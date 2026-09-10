#!/usr/bin/env python3
"""Build tagged BPM-015 procedure index (r33 clean only) and Platinum 4 packets.

  python scripts/build_miso_policy_index.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum3.playbooks import PLAYBOOKS
from src.modeling.platinum4.policy_index import STUB_RISKS, write_index
from src.modeling.platinum4.retrieve import write_sample_packets


def _refresh_playbook_sources() -> None:
    """Mark playbooks that have BPM units as bpm015_index; stubs stay stub."""
    maps = REPO / "docs" / "miso_policy" / "index" / "maps" / "risk_code_to_units.json"
    if not maps.exists():
        return
    risk_map = json.loads(maps.read_text(encoding="utf-8"))
    for code, pb in PLAYBOOKS.items():
        entry = risk_map.get(code) or {}
        if code in STUB_RISKS or not entry.get("unit_ids"):
            pb["source"] = "stub_until_policy_rag"
        else:
            pb["source"] = "bpm015_index"
    dest = REPO / "platinum3" / "results" / "playbooks.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(PLAYBOOKS, indent=2), encoding="utf-8")


def main() -> int:
    summary = write_index()
    print(json.dumps(summary, indent=2), flush=True)
    _refresh_playbook_sources()
    samples_path = REPO / "platinum3" / "results" / "sample_cards.json"
    dest = REPO / "platinum4" / "results" / "sample_bot_packets.json"
    if samples_path.exists():
        samples = json.loads(samples_path.read_text(encoding="utf-8"))
        out = write_sample_packets(samples, dest)
        print(f"wrote {out}", flush=True)
    else:
        print("skip packets: no platinum3 sample_cards.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
