#!/usr/bin/env python3
"""Phase 1 calibration layer on champion / finalist val predictions.

  python scripts/run_calibration.py
  python scripts/run_calibration.py --models catboost_tuned lightgbm_tuned
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.calibration import calibrate_model, write_calibration_report
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs

DEFAULT_MODELS = (
    "catboost_tuned",
    "lightgbm_tuned",
    "xgboost_tuned",
    "catboost",
    "survival_cox_tv",
    "survival_discrete_logistic",
    "survival_boost_lgbm",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate Phase 1 finalist probabilities (val only)")
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Model artifact names under artifacts/models/ (default: champions + survival)",
    )
    args = parser.parse_args()

    ensure_artifact_dirs()
    models = list(args.models) if args.models else list(DEFAULT_MODELS)
    results = []
    skipped = []

    for name in models:
        pred = ARTIFACTS_DIR / "models" / name / "val_predictions.parquet"
        if not pred.exists():
            print(f"[cal] skip {name}: missing {pred}", flush=True)
            skipped.append(name)
            continue
        print(f"[cal] calibrating {name} ...", flush=True)
        out = calibrate_model(name, save=True)
        results.append(out)
        best = out.get("best_method_by_cv_brier")
        methods = out.get("methods") or {}
        if best and best in methods:
            prim = (methods[best].get("cross_fitted_primary") or {})
            ops = (methods[best].get("full_val_ops") or {})
            print(
                f"  best={best} CV Brier={prim.get('brier')} ECE={prim.get('ece')} "
                f"MW@10%={ops.get('withdrawn_mw_capture_at_10pct')} "
                f"P@10%={ops.get('precision_at_10pct')}",
                flush=True,
            )

    path = write_calibration_report(results)
    summary = {
        "n_calibrated": len(results),
        "skipped": skipped,
        "report": str(path),
        "best_by_model": {r.get("model"): r.get("best_method_by_cv_brier") for r in results},
    }
    (ARTIFACTS_DIR / "metrics" / "calibration_run.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
