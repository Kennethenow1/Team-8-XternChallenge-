#!/usr/bin/env python3
"""Audit GIQ (+ EIA if present) COD-slip labels. Val-only neural-net gate: >= 200 labeled rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.gold.build_delay_training import DELAY_DIR, build_delay_gold
from src.gold.cod_delay import FOLLOWUP_MONTHS, NEURAL_NET_MIN_VAL_LABELED, audit_label_counts


def _print_audit(audit: dict) -> None:
    print("=== COD delay label audit ===")
    print(f"followup_months={audit.get('followup_months')} (Berkeley 2024 COD fields are empty)")
    print(f"n_rows={audit.get('n_rows')} have_cod_at_t={audit.get('have_cod_at_t')}")
    print("by year:")
    for y, row in (audit.get("by_year") or {}).items():
        print(
            f"  {y}: n={row['n']} labeled={row['labeled']} complete={row['complete_followup']} "
            f"share>=12m={row['share_ge_12m']} delayed_mw={row['delayed_mw']:.0f}"
        )
    print("by split:")
    for s, row in (audit.get("by_split") or {}).items():
        print(f"  {s}: n={row['n']} labeled={row['labeled']} median_slip={row['median_slip']}")
    print("event_counts", audit.get("event_counts"))
    print("GIA labeled", audit.get("gia_labeled"))
    print(f"val_labeled={audit.get('val_labeled')} (gate >= {NEURAL_NET_MIN_VAL_LABELED})")
    print("neural_nets_ok=", audit.get("neural_nets_ok"))
    print("note:", (audit.get("note") or "").encode("ascii", "replace").decode("ascii"))


def main() -> int:
    panel_path = DELAY_DIR / "cod_delay_panel.parquet"
    if panel_path.exists():
        import pandas as pd

        panel = pd.read_parquet(panel_path)
        audit = audit_label_counts(panel)
    else:
        result = build_delay_gold()
        audit = result["audit"]
    _print_audit(audit)
    out = DELAY_DIR / "label_audit.json"
    print("wrote", out)
    if not audit.get("neural_nets_ok"):
        print(
            f"GATE: val labeled < {NEURAL_NET_MIN_VAL_LABELED}. "
            "Keep trees + ridge + survival; mark TabM/FT-T/NASNet optional."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
