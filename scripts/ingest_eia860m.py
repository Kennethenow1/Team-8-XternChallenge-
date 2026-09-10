#!/usr/bin/env python3
"""Download EIA-860M monthly snapshots into bronze/silver."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.enrichment.ingest_eia860m import run_eia860m_harvest


def main() -> int:
    summary = run_eia860m_harvest()
    print(json.dumps({k: summary[k] for k in summary if k != "inventory"}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
