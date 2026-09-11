"""Complex mixed-topic Platinum 4 check: restudy + GIA/COD + DP II/D2 + stubs + GIP + diagram."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.pipeline import run_turn
from src.modeling.platinum4.session import empty_session, save_session

EXPECTED = {
    "restudy": "bpm015-r33::5.4.6",
    "dp2": "bpm015-r33::5.3.3",
    "d2": "bpm015-r33::4.2.4.5",
    "cod_delay": "bpm015-r33::7.3",
    "cod": "bpm015-r33::7.7",
    "milestone_refund": "bpm015-r33::6.2.11",
}

STUB_MARKERS = ("serial quit", "developer_serial", "FEMA", "energy-community", "energy community", "IRA")
GIP_MARKERS = ("GIP", "Attachment X", "not in this packet")

PROMPT = """
The Platinum 3 card for this interconnection request is IA Executed, the planned Commercial Operation Date has already passed, and a peer IR in the same DPP cycle has withdrawn.

Walk through all of the following in one note. Use only current BPM-015 r33. If you need Attachment X / the GIP, the GI process-flow diagram, or a superseded r32 clause, put that under Gaps and do not invent it.

1. Restudy: If MISO determines restudy is required because that peer withdrew before all GIAs/FCAs/MPFCAs for the cycle were executed or filed unexecuted, who notices, who funds the restudy, and what is the Interconnection Customer deadline to proceed or withdraw.
2. Post-GIA delay: Now that the GIA is executed and COD has already passed, which IC delay and commercial-operation clauses apply. Do not quote months of future COD slip.
3. Alternate path: If instead the IC were still at Decision Point II, what happens to DPP milestone deposits (M3/M4) and the DPP Study Funding Deposit D2 on withdrawal.
4. Stub risks: Does developer serial quit, county FEMA hazard, or IRA energy-community status change any BPM-015 duty. If there is no clause, say so.
5. Include a procedure map of who acts after the withdrawal restudy notice.

Cite each rule inline. Tariff controls if it conflicts with the BPM.
"""

FOLLOW = """
From that last note: if the IC misses the restudy notice window, is the IR deemed withdrawn under the GIP, and does the post-GIA IC-delay clause in section 7.3 still apply to this same project because COD has already passed? Answer from units already in the thread if they cover it; search only if a needed clause is missing. Keep it shorter than the full walkthrough.
"""


def _card(key: str) -> dict:
    cards = json.loads((REPO / "platinum3" / "results" / "sample_cards.json").read_text(encoding="utf-8"))
    for c in cards:
        if c.get("project_key") == key and (c.get("scenario") or {}).get("name") == "baseline":
            return c
    raise KeyError(key)


def _families(ids: list[str]) -> list[str]:
    fams = []
    for uid in ids:
        sec = uid.split("::")[-1]
        parts = sec.split(".")
        fam = ".".join(parts[:2]) if len(parts) >= 2 else sec
        if fam not in fams:
            fams.append(fam)
    return fams


def score(name: str, result: dict) -> dict:
    pkt = result["packet"]
    composed = result["composed"]
    md = composed.get("markdown") or ""
    ids = [u.get("unit_id") for u in (pkt.get("retrieved") or [])]
    hits = {k: uid for k, uid in EXPECTED.items() if uid in ids}
    return {
        "name": name,
        "searched": result.get("searched"),
        "shape": composed.get("shape"),
        "compose_mode": composed.get("compose_mode"),
        "compliance": (pkt.get("compliance") or {}).get("status"),
        "n_retrieved": len(ids),
        "ids": ids,
        "families": _families(ids),
        "hits": hits,
        "miss": [k for k in EXPECTED if k not in hits],
        "has_mermaid": "```mermaid" in md or "flowchart" in md,
        "gip_gap": any(m.lower() in md.lower() for m in GIP_MARKERS),
        "stub_honest": any(m.lower() in md.lower() for m in STUB_MARKERS)
        and ("no BPM" in md or "no clause" in md.lower() or "Gaps" in md),
        "no_r32": all("r32" not in i and "redline" not in i for i in ids),
        "invented_cites": composed.get("invented_cites") or [],
        "plan_reason": (result.get("plan") or {}).get("reason"),
        "plan_shape": (result.get("plan") or {}).get("response_shape"),
        "want_diagram": (result.get("plan") or {}).get("want_diagram"),
        "timing_ms": {
            "plan": (result.get("plan") or {}).get("elapsed_ms"),
            **{p.get("name"): p.get("elapsed_ms") for p in (composed.get("passes") or [])},
        },
        "markdown": md,
    }


def main() -> int:
    card = _card("P::B::E291")
    need = ["workflow", "stakeholders", "citations", "do_not_claim", "diagram"]
    sess = empty_session()
    r1 = run_turn(
        {
            "question": PROMPT.strip(),
            "card": card,
            "requirements": {"audience": "analyst", "dialect": "auto", "need": need, "max_units": 12},
            "split": "val",
        },
        sess,
    )
    r2 = run_turn(
        {
            "question": FOLLOW.strip(),
            "card": card,
            "requirements": {"audience": "analyst", "dialect": "auto", "need": ["workflow", "citations", "do_not_claim"], "max_units": 12},
            "split": "val",
        },
        sess,
    )
    rows = [score("complex_mix", r1), score("followup_gip_and_73", r2)]
    dest = REPO / "platinum4" / "results" / "complex_mix_check.json"
    md_dest = REPO / "platinum4" / "results" / "answers" / "complex_mix.md"
    md_dest.write_text(rows[0]["markdown"] + "\n\n---\n\n# Follow-up\n\n" + rows[1]["markdown"], encoding="utf-8")
    save_session(sess, REPO / "platinum4" / "results" / "sessions" / "complex_mix.json")
    slim = []
    for r in rows:
        slim.append({k: v for k, v in r.items() if k != "markdown"})
        print(
            f"{r['name']:22} searched={r['searched']!s:5} shape={r['shape']:12} "
            f"hits={list(r['hits'])} miss={r['miss']} mermaid={r['has_mermaid']} "
            f"gip_gap={r['gip_gap']} stub={r['stub_honest']} families={r['families']}"
        )
        print("  plan:", r["plan_reason"])
        print("  time:", r["timing_ms"])
    dest.write_text(json.dumps({"rows": slim}, indent=2, default=str), encoding="utf-8")
    print("wrote", dest)
    print("wrote", md_dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
