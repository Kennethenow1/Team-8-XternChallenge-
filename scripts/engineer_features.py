#!/usr/bin/env python3
"""Deprecated wrapper — use: python scripts/analyze_features.py --engineer-only"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analyze_features import main as analyze_main


def main() -> int:
    print("NOTE: prefer `python scripts/analyze_features.py --engineer-only`", file=sys.stderr)
    return analyze_main(["--engineer-only"])


if __name__ == "__main__":
    raise SystemExit(main())
