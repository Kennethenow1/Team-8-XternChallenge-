"""Goal-aware Optuna HPO (val-only; test sealed). CatBoost + shared helpers."""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

from src.modeling.eval_protocol import (
    SELECTION_SPLIT,
    assert_selection_split,
    distance_to_strong,
    goal_status,
)
from src.modeling.feature_policy import MACRO_FAMILY
from src.modeling.model_registry import ensure_artifact_dirs
from src.modeling.tournament_registry import (
    FAMILY_CEILINGS,
    SEEDS,
    append_live_trial,
    append_run,
    hpo_dir,
    refresh_leaderboard,
    should_stop_family,
    study_db_url,
)
from src.modeling.train_catboost import fit_catboost_eval
from src.modeling.train_lightgbm import fit_lightgbm_eval
from src.modeling.train_logistic import fit_logistic_eval
from src.modeling.train_tabm import fit_tabm_eval
from src.modeling.train_xgboost import fit_xgboost_eval


def select_finalist(trials_df: pd.DataFrame, *, top_n: int = 5) -> dict[str, Any]:
    ok = trials_df.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False)
    if ok.empty:
        raise RuntimeError("No successful Optuna trials")
    top = ok.head(top_n).copy()
    for col, higher in (("pr_auc", True), ("log_loss", False), ("brier", False), ("ece", False)):
        if col not in top.columns or top[col].isna().all():
            continue
        lo, hi = top[col].min(), top[col].max()
        if hi == lo:
            top[f"s_{col}"] = 1.0
        else:
            z = (top[col] - lo) / (hi - lo)
            top[f"s_{col}"] = z if higher else 1.0 - z
    score_cols = [c for c in ("s_pr_auc", "s_log_loss", "s_brier", "s_ece") if c in top.columns]
    top["finalist_score"] = top[score_cols].mean(axis=1) if score_cols else top["pr_auc"]
    return top.sort_values(["finalist_score", "pr_auc"], ascending=False).iloc[0].to_dict()


def load_hpo_feature_choice() -> dict[str, Any]:
    from src.modeling.model_registry import ARTIFACTS_DIR

    path = ARTIFACTS_DIR / "metrics" / "catboost_hpo_feature_set.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"feature_set": "v1", "drop_cols": []}


def suggest_catboost_params(trial: Any) -> dict[str, Any]:
    return {
        "depth": trial.suggest_int("depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 40.0, log=True),
        "random_strength": trial.suggest_float("random_strength", 0.0, 5.0),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 8.0),
        "border_count": trial.suggest_int("border_count", 32, 254),  # GPU max typically 254
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 1, 64),
        "iterations": 5000,
        "early_stopping_rounds": 100,
        "random_seed": 42,
        "verbose": False,
        "allow_writing_files": False,
        "loss_function": "Logloss",
        "eval_metric": "Logloss",
        "task_type": "GPU",
        "devices": "0",
    }


def run_goal_optuna(
    *,
    family: str,
    suggest_fn: Callable[[Any], dict[str, Any]],
    evaluate_fn: Callable[[dict[str, Any], int], dict[str, Any]],
    ceiling: int | None = None,
    seed: int = 42,
    stretch_push: bool = True,
    study_name: str | None = None,
) -> dict[str, Any]:
    """Generic goal-aware Optuna loop with resume + live logging."""
    assert_selection_split(SELECTION_SPLIT)
    import optuna

    ensure_artifact_dirs()
    ceiling = ceiling or FAMILY_CEILINGS.get(family, 500)
    storage = study_db_url(family)
    study_name = study_name or f"{family}_val_pr_auc"
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed),
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
    )

    pr_history: list[float] = [
        float(t.value) for t in study.trials if t.value is not None and t.state.name == "COMPLETE"
    ]
    best_metrics: dict[str, Any] = {}
    try:
        bt = study.best_trial
        if bt is not None and bt.user_attrs.get("metrics"):
            best_metrics = dict(bt.user_attrs["metrics"])
    except ValueError:
        pass

    n_done = len([t for t in study.trials if t.state.name == "COMPLETE"])
    print(f"[{family}] resume n_complete={n_done} ceiling={ceiling} stretch_push={stretch_push}", flush=True)

    def objective(trial: optuna.Trial) -> float:
        nonlocal best_metrics, pr_history
        params = suggest_fn(trial)
        m = evaluate_fn(params, trial.number)
        if m.get("status") != "ok":
            raise optuna.TrialPruned(str(m.get("reason")))
        clean = {k: v for k, v in m.items() if not str(k).startswith("_")}
        g = goal_status(clean)
        clean["goal"] = g
        trial.set_user_attr("metrics", clean)
        pr = float(clean["pr_auc"])
        pr_history.append(pr)
        best_pr = max(pr_history) if pr_history else pr
        if not best_metrics or pr >= float(best_metrics.get("pr_auc") or 0):
            # keep richer best by composite-ish: prefer higher pr
            best_metrics = clean
        append_live_trial(
            family,
            {
                "trial": trial.number,
                **{k: params.get(k) for k in params if k in (
                    "depth", "learning_rate", "l2_leaf_reg", "max_depth", "num_leaves",
                    "C", "l1_ratio", "min_data_in_leaf", "border_count",
                )},
                "pr_auc": clean.get("pr_auc"),
                "pr_lift": clean.get("pr_lift"),
                "roc_auc": clean.get("roc_auc"),
                "log_loss": clean.get("log_loss"),
                "brier": clean.get("brier"),
                "withdrawn_mw_capture_at_10pct": clean.get("withdrawn_mw_capture_at_10pct"),
                "best_pr_auc": best_pr,
                "goal": g,
                "plateau": False,
                "deltas": distance_to_strong(clean),
            },
        )
        append_run(
            {
                "run_id": f"{family}_hpo_{trial.number}",
                "family": family,
                "model": f"{family}_hpo",
                "status": "ok",
                "source": "optuna",
                "trial": trial.number,
                "seed": params.get("random_seed", params.get("random_state", seed)),
                **clean,
            }
        )
        return pr

    # Run in batches so we can check stop conditions
    batch = 25
    while True:
        n_done = len([t for t in study.trials if t.state.name == "COMPLETE"])
        remaining = ceiling - n_done
        if remaining <= 0:
            print(f"[{family}] STOP reason=ceiling n={n_done}", flush=True)
            break
        stop, reason = should_stop_family(
            family,
            n_completed=n_done,
            best_metrics=best_metrics or {"pr_auc": 0, "roc_auc": 0},
            pr_history=pr_history,
            stretch_push=stretch_push,
        )
        if stop:
            print(f"[{family}] STOP reason={reason} n={n_done} best_pr={best_metrics.get('pr_auc')}", flush=True)
            break
        n_batch = min(batch, remaining)
        study.optimize(objective, n_trials=n_batch, show_progress_bar=False)
        refresh_leaderboard()

    # Persist summary
    trials_rows = []
    for t in study.trials:
        if t.state.name != "COMPLETE" or t.value is None:
            continue
        m = t.user_attrs.get("metrics", {})
        trials_rows.append({"trial": t.number, "pr_auc": t.value, **t.params, **m})
    trials_df = pd.DataFrame(trials_rows)
    out_dir = hpo_dir(family)
    if not trials_df.empty:
        trials_df.to_csv(out_dir / "trials.csv", index=False)
        finalist = select_finalist(trials_df)
    else:
        finalist = {}

    summary = {
        "family": family,
        "n_complete": len(trials_rows),
        "ceiling": ceiling,
        "best_pr_auc": float(study.best_value) if study.best_trial else None,
        "best_trial": int(study.best_trial.number) if study.best_trial else None,
        "finalist": finalist,
        "best_metrics": best_metrics,
        "goal": goal_status(best_metrics) if best_metrics else "below_strong",
        "test_sealed": True,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    refresh_leaderboard()
    return summary


def run_catboost_optuna(
    *,
    n_trials: int | None = None,
    ceiling: int | None = None,
    seed: int = 42,
    feature_set: str | None = None,
    stretch_push: bool = True,
) -> dict[str, Any]:
    choice = load_hpo_feature_choice()
    if feature_set is None:
        feature_set = str(choice.get("feature_set", "v1"))
    drop_cols = list(MACRO_FAMILY) if feature_set == "v1_minus_macro" else list(choice.get("drop_cols") or [])
    ceil = ceiling or n_trials or FAMILY_CEILINGS["catboost"]

    def evaluate(params: dict[str, Any], trial_number: int) -> dict[str, Any]:
        return fit_catboost_eval(
            drop_cols=drop_cols,
            params=params,
            model_name=f"catboost_hpo_trial_{trial_number}",
            save=False,
        )

    summary = run_goal_optuna(
        family="catboost",
        suggest_fn=suggest_catboost_params,
        evaluate_fn=evaluate,
        ceiling=ceil,
        seed=seed,
        stretch_push=stretch_push,
    )

    # Multi-seed on top configs if we have trials
    trials_path = hpo_dir("catboost") / "trials.csv"
    if trials_path.exists():
        tdf = pd.read_csv(trials_path)
        top = tdf.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False).head(5)
        seed_rows = []
        for _, row in top.iterrows():
            base_params = suggest_catboost_params.__wrapped__ if False else {
                "depth": int(row["depth"]),
                "learning_rate": float(row["learning_rate"]),
                "l2_leaf_reg": float(row["l2_leaf_reg"]),
                "random_strength": float(row["random_strength"]),
                "bagging_temperature": float(row["bagging_temperature"]),
                "iterations": 5000,
                "early_stopping_rounds": 100,
                "verbose": False,
                "allow_writing_files": False,
                "loss_function": "Logloss",
                "eval_metric": "Logloss",
                "task_type": "GPU",
                "devices": "0",
            }
            if "border_count" in row and pd.notna(row["border_count"]):
                base_params["border_count"] = int(row["border_count"])
            if "min_data_in_leaf" in row and pd.notna(row["min_data_in_leaf"]):
                base_params["min_data_in_leaf"] = int(row["min_data_in_leaf"])
            for s in SEEDS:
                p = {**base_params, "random_seed": int(s)}
                m = fit_catboost_eval(drop_cols=drop_cols, params=p, model_name=f"catboost_seed_{s}", save=False)
                clean = {k: v for k, v in m.items() if not str(k).startswith("_")}
                seed_rows.append({"parent_trial": int(row["trial"]), "seed": s, **clean})
                print(f"[catboost] seed={s} parent={int(row['trial'])} pr={clean.get('pr_auc')} goal={goal_status(clean)}", flush=True)
                append_run({
                    "run_id": f"catboost_seed_{int(row['trial'])}_{s}",
                    "family": "catboost",
                    "model": "catboost_multiseed",
                    "status": clean.get("status", "ok"),
                    "source": "multiseed",
                    "seed": s,
                    **clean,
                })
        sdf = pd.DataFrame(seed_rows)
        sdf.to_csv(hpo_dir("catboost") / "multiseed.csv", index=False)
        # Promote best mean-PR config's best seed run
        if not sdf.empty:
            means = sdf.groupby("parent_trial")["pr_auc"].mean().sort_values(ascending=False)
            best_parent = int(means.index[0])
            best_row = sdf[sdf["parent_trial"] == best_parent].sort_values("pr_auc", ascending=False).iloc[0]
            parent = top[top["trial"] == best_parent].iloc[0]
            promo_params = {
                "depth": int(parent["depth"]),
                "learning_rate": float(parent["learning_rate"]),
                "l2_leaf_reg": float(parent["l2_leaf_reg"]),
                "random_strength": float(parent["random_strength"]),
                "bagging_temperature": float(parent["bagging_temperature"]),
                "iterations": 5000,
                "early_stopping_rounds": 100,
                "random_seed": int(best_row["seed"]),
                "verbose": False,
                "allow_writing_files": False,
                "loss_function": "Logloss",
                "eval_metric": "Logloss",
                "task_type": "GPU",
                "devices": "0",
            }
            promoted = fit_catboost_eval(
                drop_cols=drop_cols,
                params=promo_params,
                model_name="catboost_tuned",
                save=True,
            )
            summary["promoted"] = {k: v for k, v in promoted.items() if not str(k).startswith("_")}
            summary["multiseed_best_parent"] = best_parent
            summary["multiseed_mean_pr"] = float(means.iloc[0])
            (hpo_dir("catboost") / "summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
            append_run({
                "run_id": "catboost_tuned_promoted",
                "family": "catboost",
                "model": "catboost_tuned",
                "status": "ok",
                "source": "promoted",
                **summary["promoted"],
            })
            refresh_leaderboard()
    return summary


def suggest_lightgbm_params(trial: Any) -> dict[str, Any]:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "n_estimators": 5000,
        "early_stopping_rounds": 100,
        "objective": "binary",
        "metric": "binary_logloss",
        "random_state": 42,
        "n_jobs": 4,
        "verbosity": -1,
    }


def run_lightgbm_optuna(
    *,
    ceiling: int | None = None,
    seed: int = 42,
    stretch_push: bool = True,
) -> dict[str, Any]:
    ceil = ceiling or FAMILY_CEILINGS["lightgbm"]

    def evaluate(params: dict[str, Any], trial_number: int) -> dict[str, Any]:
        return fit_lightgbm_eval(
            params=params,
            model_name=f"lightgbm_hpo_trial_{trial_number}",
            save=False,
        )

    summary = run_goal_optuna(
        family="lightgbm",
        suggest_fn=suggest_lightgbm_params,
        evaluate_fn=evaluate,
        ceiling=ceil,
        seed=seed,
        stretch_push=stretch_push,
    )

    trials_path = hpo_dir("lightgbm") / "trials.csv"
    if trials_path.exists():
        tdf = pd.read_csv(trials_path)
        top = tdf.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False).head(1)
        if not top.empty:
            row = top.iloc[0]
            promo_params = {
                "learning_rate": float(row["learning_rate"]),
                "num_leaves": int(row["num_leaves"]),
                "max_depth": int(row["max_depth"]),
                "min_child_samples": int(row["min_child_samples"]),
                "subsample": float(row["subsample"]),
                "colsample_bytree": float(row["colsample_bytree"]),
                "reg_alpha": float(row["reg_alpha"]),
                "reg_lambda": float(row["reg_lambda"]),
                "n_estimators": 5000,
                "early_stopping_rounds": 100,
                "objective": "binary",
                "metric": "binary_logloss",
                "random_state": 42,
                "n_jobs": 4,
                "verbosity": -1,
            }
            promoted = fit_lightgbm_eval(params=promo_params, model_name="lightgbm_tuned", save=True)
            summary["promoted"] = {k: v for k, v in promoted.items() if not str(k).startswith("_")}
            (hpo_dir("lightgbm") / "summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
            append_run({
                "run_id": "lightgbm_tuned_promoted",
                "family": "lightgbm",
                "model": "lightgbm_tuned",
                "status": "ok",
                "source": "promoted",
                **summary["promoted"],
            })
            refresh_leaderboard()
    return summary


def suggest_xgboost_params(trial: Any) -> dict[str, Any]:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "gamma": trial.suggest_float("gamma", 1e-8, 5.0, log=True),
        "n_estimators": 5000,
        "early_stopping_rounds": 100,
        "objective": "binary:logistic",
        "tree_method": "hist",
        "eval_metric": "logloss",
        "random_state": 42,
        "n_jobs": 4,
    }


def run_xgboost_optuna(
    *,
    ceiling: int | None = None,
    seed: int = 42,
    stretch_push: bool = True,
) -> dict[str, Any]:
    ceil = ceiling or FAMILY_CEILINGS["xgboost"]

    def evaluate(params: dict[str, Any], trial_number: int) -> dict[str, Any]:
        return fit_xgboost_eval(
            params=params,
            model_name=f"xgboost_hpo_trial_{trial_number}",
            save=False,
        )

    summary = run_goal_optuna(
        family="xgboost",
        suggest_fn=suggest_xgboost_params,
        evaluate_fn=evaluate,
        ceiling=ceil,
        seed=seed,
        stretch_push=stretch_push,
    )

    trials_path = hpo_dir("xgboost") / "trials.csv"
    if trials_path.exists():
        tdf = pd.read_csv(trials_path)
        top = tdf.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False).head(1)
        if not top.empty:
            row = top.iloc[0]
            promo_params = {
                "learning_rate": float(row["learning_rate"]),
                "max_depth": int(row["max_depth"]),
                "min_child_weight": int(row["min_child_weight"]),
                "subsample": float(row["subsample"]),
                "colsample_bytree": float(row["colsample_bytree"]),
                "reg_alpha": float(row["reg_alpha"]),
                "reg_lambda": float(row["reg_lambda"]),
                "gamma": float(row["gamma"]),
                "n_estimators": 5000,
                "early_stopping_rounds": 100,
                "objective": "binary:logistic",
                "tree_method": "hist",
                "eval_metric": "logloss",
                "random_state": 42,
                "n_jobs": 4,
            }
            promoted = fit_xgboost_eval(params=promo_params, model_name="xgboost_tuned", save=True)
            summary["promoted"] = {k: v for k, v in promoted.items() if not str(k).startswith("_")}
            (hpo_dir("xgboost") / "summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
            append_run({
                "run_id": "xgboost_tuned_promoted",
                "family": "xgboost",
                "model": "xgboost_tuned",
                "status": "ok",
                "source": "promoted",
                **summary["promoted"],
            })
            refresh_leaderboard()
    return summary


def suggest_logistic_params(trial: Any) -> dict[str, Any]:
    use_l2 = trial.suggest_categorical("use_l2", [True, False])
    if use_l2:
        l1_ratio = 0.0
        penalty = "l2"
    else:
        l1_ratio = trial.suggest_float("l1_ratio", 0.1, 1.0)
        penalty = "elasticnet"
    return {
        "C": trial.suggest_float("C", 1e-3, 100.0, log=True),
        "l1_ratio": l1_ratio,
        "penalty": penalty,
    }


def run_logistic_optuna(
    *,
    ceiling: int | None = None,
    seed: int = 42,
    stretch_push: bool = False,
) -> dict[str, Any]:
    ceil = ceiling or FAMILY_CEILINGS["logistic"]

    def evaluate(params: dict[str, Any], trial_number: int) -> dict[str, Any]:
        return fit_logistic_eval(
            name=f"logistic_hpo_trial_{trial_number}",
            penalty=str(params["penalty"]),
            C=float(params["C"]),
            l1_ratio=float(params["l1_ratio"]),
            save=False,
        )

    summary = run_goal_optuna(
        family="logistic",
        suggest_fn=suggest_logistic_params,
        evaluate_fn=evaluate,
        ceiling=ceil,
        seed=seed,
        stretch_push=stretch_push,
    )

    trials_path = hpo_dir("logistic") / "trials.csv"
    if trials_path.exists():
        tdf = pd.read_csv(trials_path)
        top = tdf.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False).head(1)
        if not top.empty:
            row = top.iloc[0]
            if "use_l2" in row.index and bool(row["use_l2"]):
                l1 = 0.0
                penalty = "l2"
            else:
                l1 = float(row.get("l1_ratio", 0.5))
                penalty = "elasticnet"
            promoted = fit_logistic_eval(
                name="logistic_tuned",
                penalty=penalty,
                C=float(row["C"]),
                l1_ratio=l1,
                save=True,
            )
            summary["promoted"] = {k: v for k, v in promoted.items() if not str(k).startswith("_")}
            (hpo_dir("logistic") / "summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
            append_run({
                "run_id": "logistic_tuned_promoted",
                "family": "logistic",
                "model": "logistic_tuned",
                "status": "ok",
                "source": "promoted",
                **summary["promoted"],
            })
            refresh_leaderboard()
    return summary


def suggest_tabm_params(trial: Any) -> dict[str, Any]:
    return {
        "k": trial.suggest_categorical("k", [8, 16, 32]),
        "n_blocks": trial.suggest_int("n_blocks", 2, 4),
        "d_block": trial.suggest_categorical("d_block", [256, 512]),
        "dropout": trial.suggest_float("dropout", 0.0, 0.3),
        "lr": trial.suggest_float("lr", 5e-4, 5e-3, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-5, 1e-2, log=True),
        "batch_size": trial.suggest_categorical("batch_size", [128, 256, 512]),
        "patience": 12,
        "max_epochs": 80,
        "seed": 42,
    }


def run_tabm_optuna(
    *,
    ceiling: int | None = None,
    seed: int = 42,
    stretch_push: bool = True,
) -> dict[str, Any]:
    """TabM HPO; returns skip summary if official tabm package unavailable."""
    try:
        import tabm  # noqa: F401
    except ImportError as e:
        summary = {
            "family": "tabm",
            "status": "skipped",
            "reason": f"tabm not installed: {e}",
            "n_complete": 0,
            "test_sealed": True,
        }
        out_dir = hpo_dir("tabm")
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[tabm] SKIP reason={summary['reason']}", flush=True)
        return summary

    ceil = ceiling or FAMILY_CEILINGS["tabm"]

    def evaluate(params: dict[str, Any], trial_number: int) -> dict[str, Any]:
        return fit_tabm_eval(
            params={**params, "seed": seed},
            model_name=f"tabm_hpo_trial_{trial_number}",
            save=False,
        )

    summary = run_goal_optuna(
        family="tabm",
        suggest_fn=suggest_tabm_params,
        evaluate_fn=evaluate,
        ceiling=ceil,
        seed=seed,
        stretch_push=stretch_push,
    )

    trials_path = hpo_dir("tabm") / "trials.csv"
    if trials_path.exists():
        tdf = pd.read_csv(trials_path)
        top = tdf.dropna(subset=["pr_auc"]).sort_values("pr_auc", ascending=False).head(1)
        if not top.empty:
            row = top.iloc[0]
            promo_params = {
                "k": int(row["k"]),
                "n_blocks": int(row["n_blocks"]),
                "d_block": int(row["d_block"]),
                "dropout": float(row["dropout"]),
                "lr": float(row["lr"]),
                "weight_decay": float(row["weight_decay"]),
                "batch_size": int(row["batch_size"]),
                "patience": 16,
                "max_epochs": 200,
                "seed": seed,
            }
            promoted = fit_tabm_eval(params=promo_params, model_name="tabm_tuned", save=True)
            if promoted.get("status") == "ok":
                summary["promoted"] = {k: v for k, v in promoted.items() if not str(k).startswith("_")}
                (hpo_dir("tabm") / "summary.json").write_text(
                    json.dumps(summary, indent=2, default=str), encoding="utf-8"
                )
                append_run({
                    "run_id": "tabm_tuned_promoted",
                    "family": "tabm",
                    "model": "tabm_tuned",
                    "status": "ok",
                    "source": "promoted",
                    **summary["promoted"],
                })
                refresh_leaderboard()
    return summary
