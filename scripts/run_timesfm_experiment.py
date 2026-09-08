#!/usr/bin/env python3
"""TimesFM / baseline system monthly forecast experiment.

  python scripts/run_timesfm_experiment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.train_timesfm import run_timesfm_experiment


def main() -> int:
    result = run_timesfm_experiment(save=True)
    print(json.dumps({"n_folds": result.get("n_folds"), "models": result.get("models")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
