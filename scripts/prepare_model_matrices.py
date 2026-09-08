#!/usr/bin/env python3
"""Fit train-only impute/scale; write logistic/tree/foundation model matrices.

  python scripts/prepare_model_matrices.py

Also emits foundation_v1_* (native categoricals, no scale) for TabICL / TabPFN / TabM.
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
