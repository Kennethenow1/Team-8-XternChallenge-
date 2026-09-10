#!/usr/bin/env python3
"""Val-only Platinum HPO. Objective = MAE (minimize). Never unseals test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CEILINGS = {"logistic": 40, "catboost": 400, "lightgbm": 250, "xgboost": 250, "tabm": 80}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--family", choices=list(CEILINGS), default="catboost")
    p.add_argument("--trials", type=int, default=20)
    args = p.parse_args()

    from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

    assert_selection_split(SELECTION_SPLIT)
    n = min(int(args.trials), CEILINGS[args.family])

    try:
        import optuna
    except ImportError:
        print("optuna not installed; writing default-recipe note")
        out = REPO / "data" / "gold" / "delay" / "modeling" / "artifacts" / "hpo"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{args.family}_skipped.json").write_text(json.dumps({"status": "skipped", "reason": "optuna missing"}), encoding="utf-8")
        return 0

    def objective(trial: "optuna.Trial") -> float:
        if args.family == "logistic":
            from src.modeling.delay.train_ridge import fit_ridge_eval

            m = fit_ridge_eval(
                alpha=trial.suggest_float("alpha", 1e-3, 100, log=True),
                l1_ratio=trial.suggest_categorical("l1_ratio", [0.0, 0.5, 0.9]),
            )
        elif args.family == "catboost":
            from src.modeling.delay.train_catboost import fit_catboost_delay

            m = fit_catboost_delay(
                params={
                    "depth": trial.suggest_int("depth", 4, 8),
                    "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
                    "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 20),
                    "random_strength": trial.suggest_float("random_strength", 0, 5),
                    "bagging_temperature": trial.suggest_float("bagging_temperature", 0, 8),
                    "border_count": trial.suggest_int("border_count", 64, 254),
                    "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 8, 64),
                }
            )
        elif args.family == "lightgbm":
            from src.modeling.delay.train_lightgbm import fit_lightgbm_delay

            m = fit_lightgbm_delay(
                params={
                    "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                    "max_depth": trial.suggest_int("max_depth", 3, 8),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
                    "min_child_samples": trial.suggest_int("min_child_samples", 20, 80),
                }
            )
        elif args.family == "xgboost":
            from src.modeling.delay.train_xgboost import fit_xgboost_delay

            m = fit_xgboost_delay(
                params={
                    "max_depth": trial.suggest_int("max_depth", 3, 8),
                    "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.1, log=True),
                    "min_child_weight": trial.suggest_int("min_child_weight", 4, 20),
                    "gamma": trial.suggest_float("gamma", 0, 1),
                }
            )
        else:
            from src.modeling.delay.train_tabm import fit_tabm_delay

            m = fit_tabm_delay(
                max_epochs=80,
                patience=12,
                k=trial.suggest_categorical("k", [8, 16, 32]),
                n_blocks=trial.suggest_int("n_blocks", 2, 4),
                d_block=trial.suggest_categorical("d_block", [256, 512]),
                lr=trial.suggest_float("lr", 5e-4, 5e-3, log=True),
                dropout=trial.suggest_float("dropout", 0.0, 0.3),
            )
        mae = m.get("mae")
        if mae is None or m.get("status") != "ok":
            raise optuna.TrialPruned(str(m.get("reason")))
        trial.set_user_attr("companion_pr_auc", m.get("companion_pr_auc"))
        trial.set_user_attr("pinball80", m.get("pinball80"))
        return float(mae)

    study = optuna.create_study(direction="minimize", study_name=f"platinum_{args.family}")
    study.optimize(objective, n_trials=n, catch=(Exception,))
    out = REPO / "data" / "gold" / "delay" / "modeling" / "artifacts" / "hpo"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "family": args.family,
        "n_trials": n,
        "best_mae": study.best_value if study.best_trial else None,
        "best_params": study.best_params if study.best_trial else None,
        "best_companion_pr_auc": (study.best_trial.user_attrs.get("companion_pr_auc") if study.best_trial else None),
    }
    (out / f"{args.family}_summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
