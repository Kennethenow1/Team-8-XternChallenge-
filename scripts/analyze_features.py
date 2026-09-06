#!/usr/bin/env python3
"""Train-only feature analysis + approved engineering transforms / macro audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.feature_analysis import run_feature_analysis
from src.modeling.feature_engineering import run_feature_engineering


def main() -> int:
    print("=== Feature analysis (inventory / corr / preview) ===")
    analysis = run_feature_analysis()
    print(json.dumps({k: analysis[k] for k in (
        "train_complete_rows",
        "numeric_preview_shape",
        "n_high_corr_pairs",
        "all_preview_features_numeric",
    ) if k in analysis}, indent=2))

    print("\n=== Feature engineering (collapses + audits) ===")
    eng = run_feature_engineering()
    print(json.dumps(eng, indent=2, default=str))
    print(f"\nRegularized train set: {eng['manifest']['regularized_path']}")
    print(f"Reports: {eng.get('reports_dir')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
