#!/usr/bin/env python3
"""Fit train-only delay matrices (logistic / tree / catboost / foundation / tabm / seq)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.delay_matrices import prepare_delay_matrices


def main() -> int:
    summary = prepare_delay_matrices()
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
