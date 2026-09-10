#!/usr/bin/env python3
"""Rebuild EIA-860M silver (full quarterlies) and Platinum 2 delayed-MW gold series."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.enrichment.ingest_eia860m import run_eia860m_harvest
from src.gold.gia_delayed_mw_series import build_platinum2_gold


def main() -> int:
    harvest = run_eia860m_harvest()
    n_snaps = len(harvest.get("snapshots") or [])
    print(json.dumps({k: harvest[k] for k in harvest if k != "inventory"}, indent=2, default=str))
    if harvest.get("status") != "ok" or n_snaps < 12:
        print(f"STOP: need ≥12 EIA snapshots, got {n_snaps}. Not training TimesFM on a stub.", flush=True)
        return 2
    out = build_platinum2_gold()
    print(json.dumps(out["audit"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
