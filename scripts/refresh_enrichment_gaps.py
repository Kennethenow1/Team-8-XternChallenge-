#!/usr/bin/env python3
"""Deprecated wrapper — use: python scripts/run_enrichment.py gaps"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_enrichment import main as enrichment_main


def main() -> int:
    print("NOTE: prefer `python scripts/run_enrichment.py gaps`", file=sys.stderr)
    return enrichment_main(["gaps"])


if __name__ == "__main__":
    raise SystemExit(main())
