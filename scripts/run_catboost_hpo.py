#!/usr/bin/env python3
"""Goal-aware CatBoost HPO (resume + live progress).

  python scripts/run_catboost_hpo.py --ceiling 1500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.tune import run_catboost_optuna


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ceiling", type=int, default=1500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-stretch", action="store_true")
    p.add_argument("--feature-set", choices=("v1", "v1_minus_macro"), default=None)
    args = p.parse_args()
    summary = run_catboost_optuna(
        ceiling=args.ceiling,
        seed=args.seed,
        feature_set=args.feature_set,
        stretch_push=not args.no_stretch,
    )
    print(json.dumps({k: summary.get(k) for k in (
        "family", "n_complete", "best_pr_auc", "goal", "promoted", "multiseed_mean_pr"
    )}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
