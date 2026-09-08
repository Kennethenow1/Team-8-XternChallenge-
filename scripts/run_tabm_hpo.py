#!/usr/bin/env python3
"""Goal-aware TabM HPO (resume + live progress).

Skips cleanly if official `tabm` package is not installed.

  python scripts/run_tabm_hpo.py --ceiling 700
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.tune import run_tabm_optuna


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ceiling", type=int, default=700)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-stretch", action="store_true")
    args = p.parse_args()
    summary = run_tabm_optuna(
        ceiling=args.ceiling,
        seed=args.seed,
        stretch_push=not args.no_stretch,
    )
    print(json.dumps({k: summary.get(k) for k in (
        "family", "status", "reason", "n_complete", "best_pr_auc", "goal", "promoted"
    )}, indent=2, default=str))
    return 0 if summary.get("status") != "skipped" else 0


if __name__ == "__main__":
    raise SystemExit(main())
