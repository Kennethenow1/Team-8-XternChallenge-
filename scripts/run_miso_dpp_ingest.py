#!/usr/bin/env python3
"""Acquire and extract historical MISO DPP GI studies. Does not merge into Gold."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.enrichment.ingest_miso_dpp import run_miso_dpp_ingest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip Playwright network capture (still uses Optics API index).",
    )
    args = parser.parse_args()
    run_miso_dpp_ingest(skip_playwright=args.skip_playwright)


if __name__ == "__main__":
    main()
