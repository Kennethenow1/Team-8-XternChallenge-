#!/usr/bin/env python3
"""EIA-860M harvest + FERC-730 best-effort + delay gold + delay matrices."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    from src.enrichment.ingest_eia860m import run_eia860m_harvest
    from src.enrichment.ingest_ferc730 import run_ferc730_harvest
    from src.gold.build_delay_training import build_delay_gold
    from src.modeling.delay_matrices import prepare_delay_matrices

    eia = run_eia860m_harvest()
    print("EIA-860M:", json.dumps({k: eia[k] for k in eia if k != "inventory"}, default=str))
    ferc = run_ferc730_harvest()
    print("FERC-730:", ferc.get("status"))
    gold = build_delay_gold()
    mats = prepare_delay_matrices()
    print("matrices:", json.dumps(mats, indent=2, default=str)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
