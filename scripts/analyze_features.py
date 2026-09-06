#!/usr/bin/env python3
"""Train-only feature analysis + approved engineering transforms / macro audit.

  python scripts/analyze_features.py              # analysis then engineering
  python scripts/analyze_features.py --engineer-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.feature_analysis import run_feature_analysis
from src.modeling.feature_engineering import run_feature_engineering
from src.modeling.preprocessing import run_preprocessing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engineer-only",
        action="store_true",
        help="Skip inventory/corr preview; only apply engineering transforms.",
    )
    parser.add_argument(
        "--skip-prep",
        action="store_true",
        help="Skip train-only impute/scale logistic/tree matrix prep.",
    )
    args = parser.parse_args(argv)

    if not args.engineer_only:
        print("=== Feature analysis (inventory / corr / preview) ===")
        analysis = run_feature_analysis()
        print(json.dumps({k: analysis[k] for k in (
            "train_complete_rows",
            "numeric_preview_shape",
            "n_high_corr_pairs",
            "all_preview_features_numeric",
        ) if k in analysis}, indent=2))
        print()

    print("=== Feature engineering (collapses + audits) ===")
    eng = run_feature_engineering()
    print(json.dumps({k: eng[k] for k in ("model_ready_paths", "macro_recommendation", "schema_role_counts") if k in eng}, indent=2, default=str))
    print(f"\nModel-ready train set: {eng['manifest']['model_ready_path']}")
    print(f"Schema/readiness: {eng['manifest'].get('readiness_path')}")

    if not args.skip_prep:
        print("\n=== Preprocessing (logistic impute+scale / tree leave NaNs) ===")
        prep = run_preprocessing()
        print(json.dumps({k: prep[k] for k in ("nan_check", "n_features", "n_impute", "n_scale", "sparse_flags") if k in prep}, indent=2, default=str))

    print(f"Reports: {eng.get('reports_dir')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
