#!/usr/bin/env python3
"""Apply approved feature collapses and write train_regularized modeling matrix."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.feature_engineering import run_feature_engineering


def main() -> int:
    summary = run_feature_engineering()
    print(json.dumps(summary, indent=2, default=str))
    print(f"\nRegularized: {summary['manifest']['regularized_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
