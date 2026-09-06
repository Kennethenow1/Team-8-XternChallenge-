#!/usr/bin/env python3
"""Fit train-only impute/scale; write logistic_ready_* and tree_ready_* matrices.

  python scripts/prepare_model_matrices.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.preprocessing import run_preprocessing


def main() -> int:
    summary = run_preprocessing()
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
