#!/usr/bin/env python3
"""AutoGluon Tabular benchmark on forced train/val frames (val-only selection).

  python scripts/run_autogluon_benchmark.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs, load_capacity_mw, load_xy, save_run_artifacts
from src.modeling.tournament_registry import append_run, refresh_leaderboard


def main() -> int:
    assert_selection_split(SELECTION_SPLIT)
    ensure_artifact_dirs()

    try:
        from autogluon.tabular import TabularPredictor
    except ImportError as e:
        result = {"status": "skipped", "reason": f"autogluon.tabular not installed: {e}"}
        out = ARTIFACTS_DIR / "metrics" / "autogluon_benchmark.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0

    X_tr, y_tr, _ = load_xy("tree_v1", "train")
    X_va, y_va, meta_va = load_xy("tree_v1", SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    train_df = X_tr.loc[mask].copy()
    train_df["withdraw_next_12m"] = y_tr.loc[mask].astype(int)
    val_df = X_va.copy()
    val_df["withdraw_next_12m"] = y_va.astype(int)

    presets = ["medium_quality", "good_quality", "best_quality"]
    results = []

    for preset in presets:
        model_name = f"autogluon_{preset}"
        print(f"=== AutoGluon preset={preset} ===", flush=True)
        with tempfile.TemporaryDirectory(prefix="ag_benchmark_") as tmp:
            try:
                pred = TabularPredictor(
                    label="withdraw_next_12m",
                    problem_type="binary",
                    eval_metric="log_loss",
                    path=tmp,
                )
                # Fair protocol: fit on train only; score val once (no val leakage into fit).
                pred.fit(
                    train_df,
                    presets=preset,
                    time_limit=180 if preset == "medium_quality" else 300,
                    verbosity=0,
                )
                proba = pred.predict_proba(val_df.drop(columns=["withdraw_next_12m"])).iloc[:, 1]
            except Exception as e:  # noqa: BLE001
                rec = {"preset": preset, "status": "skipped", "reason": str(e)}
                results.append(rec)
                append_run(
                    {
                        "run_id": f"autogluon_{preset}",
                        "family": "autogluon",
                        "model": model_name,
                        "status": "skipped",
                        "reason": str(e),
                        "source": "autogluon_benchmark",
                        "split": "val",
                        "test_sealed": True,
                    }
                )
                print(f"  SKIPPED: {e}", flush=True)
                continue

        capacity = load_capacity_mw(meta_va)
        metrics = full_eval_metrics(y_va.astype(float), proba.to_numpy(), capacity)
        metrics.update({"status": "ok", "model": model_name, "preset": preset, "split": SELECTION_SPLIT})
        preds = meta_va.copy()
        preds["y_true"] = y_va.to_numpy()
        preds["y_prob"] = proba.to_numpy()
        save_run_artifacts(
            model_name,
            hyperparams={"preset": preset, "eval_metric": "log_loss"},
            feature_list={"feature_columns": list(X_tr.columns), "n": len(X_tr.columns)},
            train_metadata={"matrix": "tree_v1", "n_train": len(train_df), "n_val": len(val_df)},
            metrics=metrics,
            val_predictions=preds,
        )
        rec = {"preset": preset, **metrics}
        results.append(rec)
        append_run(
            {
                "run_id": f"autogluon_{preset}",
                "family": "autogluon",
                "model": model_name,
                "status": "ok",
                "source": "autogluon_benchmark",
                "split": "val",
                "test_sealed": True,
                **{k: metrics.get(k) for k in ("pr_auc", "roc_auc", "brier", "log_loss", "pr_lift")},
            }
        )
        print(f"  pr_auc={metrics.get('pr_auc')} log_loss={metrics.get('log_loss')}", flush=True)

    md_lines = [
        "# AutoGluon benchmark (validation only)",
        "",
        "**Test / score sealed.** Tuning data = val (forced frames).",
        "",
        "| preset | status | pr_auc | log_loss |",
        "|--------|--------|--------|----------|",
    ]
    for r in results:
        md_lines.append(
            f"| {r.get('preset')} | {r.get('status', 'ok')} | {r.get('pr_auc')} | {r.get('log_loss', r.get('reason'))} |"
        )
    md_path = ARTIFACTS_DIR / "metrics" / "autogluon_benchmark.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    (ARTIFACTS_DIR / "metrics" / "autogluon_benchmark.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    refresh_leaderboard()
    print(json.dumps({"md": str(md_path), "n_presets": len(presets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
