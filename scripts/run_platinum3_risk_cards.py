#!/usr/bin/env python3
"""Build Platinum 3 risk cards (val by default). Does not train a new contest model.

  python scripts/run_platinum3_risk_cards.py
  python scripts/run_platinum3_risk_cards.py --split score
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum3.cards import build_risk_cards, write_risk_card_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Platinum 3 risk-card peripherals (no new trainer)")
    parser.add_argument("--split", default="val", help="val (default) or score. test is sealed.")
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help="Subset of scenario names. Default: all.",
    )
    args = parser.parse_args()
    if args.split == "test":
        print("REFUSED: test is sealed. Use --split val or --split score.", flush=True)
        return 2
    print(f"[platinum3] split={args.split} building risk cards ...", flush=True)
    bundle = build_risk_cards(split=args.split, scenarios=args.scenarios)
    outputs = write_risk_card_bundle(bundle)
    summary = {
        "schema_version": bundle.get("schema_version"),
        "split": bundle.get("split"),
        "n_rows": bundle.get("n_rows"),
        "n_cards": bundle.get("n_cards"),
        "scorer_source": bundle.get("scorer_source"),
        "calibration_note": bundle.get("calibration_note"),
        "scenario_sensitivity_val_only": bundle.get("scenario_sensitivity_val_only"),
        "outputs": outputs,
        "test_sealed": True,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
