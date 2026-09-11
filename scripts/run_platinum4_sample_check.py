"""Sample-check Platinum 4 pipeline on the three val projects. Not a contest eval."""

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

SAMPLES = json.loads((REPO / "platinum3" / "results" / "sample_cards.json").read_text(encoding="utf-8"))
OUT = REPO / "platinum4" / "results" / "sample_check.json"


def card(key: str) -> dict:
    for c in SAMPLES:
        if c.get("project_key") == key and (c.get("scenario") or {}).get("name") == "baseline":
            return c
    raise KeyError(key)


def query(question: str, key: str | None = None) -> dict:
    return {
        "question": question,
        "card": card(key) if key else None,
        "requirements": {
            "audience": "analyst",
            "dialect": "auto",
            "need": ["workflow", "stakeholders", "citations", "do_not_claim"],
            "max_units": 12,
        },
        "split": "val",
    }


def gauge(name: str, result: dict, expected: list[str]) -> dict:
    pkt = result["packet"]
    composed = result["composed"]
    md = composed.get("markdown") or ""
    ids = [u.get("unit_id") for u in (pkt.get("retrieved") or [])]
    hits = [e for e in expected if e in ids]
    miss = [e for e in expected if e not in ids]
    timing = {p.get("name"): p.get("elapsed_ms") for p in (composed.get("passes") or [])}
    if result.get("plan"):
        timing["plan"] = (result["plan"] or {}).get("elapsed_ms")
    return {
        "name": name,
        "question": (pkt.get("query") or {}).get("question"),
        "project_key": (pkt.get("card") or {}).get("project_key"),
        "searched": result.get("searched"),
        "shape": composed.get("shape"),
        "compose_mode": composed.get("compose_mode"),
        "compliance": (pkt.get("compliance") or {}).get("status"),
        "expected": expected,
        "hit": hits,
        "miss": miss,
        "hit_rate": (len(hits) / len(expected)) if expected else None,
        "n_retrieved": len(ids),
        "top_ids": ids[:6],
        "invented_cites": composed.get("invented_cites") or [],
        "error_code": composed.get("error_code") or pkt.get("error_code"),
        "has_compliance_line": "Compliance: not_determined" in md,
        "mentions_ic": bool(re.search(r"Interconnection Customer|\(IC\)", md)),
        "mentions_miso": bool(re.search(r"\bMISO\b", md)),
        "n_sentences": len([s for s in re.split(r"(?<=[.!?])\s+", md.strip()) if s.strip()]),
        "timing_ms": timing,
        "plan_reason": (result.get("plan") or {}).get("reason"),
        "plan_source": (result.get("plan") or {}).get("source"),
        "excerpt": " ".join(md.split())[:360],
    }


def main() -> int:
    rows = []
    notes = []
    sess = empty_session()

    r1 = run_turn(
        query("Who funds a restudy if a peer withdraws?", "P::B::E291"),
        sess,
    )
    rows.append(gauge("restudy_funding", r1, ["bpm015-r33::5.4.6"]))
    notes.append(("restudy_funding", r1))

    r2 = run_turn(
        query("Who pays for that, and how many Business Days does the IC have to answer?"),
        sess,
    )
    rows.append(gauge("restudy_followup", r2, ["bpm015-r33::5.4.6"]))
    notes.append(("restudy_followup", r2))

    sess_b = empty_session()
    r3 = run_turn(
        query("What happens at Decision Point II?", "P::J2280"),
        sess_b,
    )
    rows.append(gauge("decision_point_ii", r3, ["bpm015-r33::5.3.3"]))
    notes.append(("decision_point_ii", r3))

    sess_c = empty_session()
    r4 = run_turn(
        query("What delay clauses apply after GIA when COD has already passed?", "P::B::E291"),
        sess_c,
    )
    rows.append(gauge("gia_cod_delay", r4, ["bpm015-r33::7.3", "bpm015-r33::7.7"]))
    notes.append(("gia_cod_delay", r4))

    sess_d = empty_session()
    r5 = run_turn(
        query("What is the DPP Study Funding Deposit D2?", "P::J2460"),
        sess_d,
    )
    rows.append(gauge("d2_deposit", r5, ["bpm015-r33::4.2.4.5"]))
    notes.append(("d2_deposit", r5))

    save_session(sess, REPO / "platinum4" / "results" / "sessions" / "sample_check.json")
    notes_path = REPO / "platinum4" / "results" / "answers" / "sample_check_notes.md"
    chunks = []
    for name, result in notes:
        md = (result.get("composed") or {}).get("markdown") or ""
        q = (result.get("packet") or {}).get("query") or {}
        chunks.append(f"# {name}\n\nQuestion: {q.get('question')}\n\n{md.strip()}\n")
    notes_path.write_text("\n---\n\n".join(chunks), encoding="utf-8")
    print("wrote", notes_path)
    summary = {
        "n": len(rows),
        "n_full_hit": sum(1 for r in rows if not r["miss"]),
        "n_compliance": sum(1 for r in rows if r["compliance"] == "not_determined"),
        "n_invented": sum(1 for r in rows if r["invented_cites"]),
        "n_followup_no_search": sum(1 for r in rows if r["name"] == "restudy_followup" and r["searched"] is False),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    for r in rows:
        print(
            f"{r['name']:20} searched={r['searched']!s:5} shape={r['shape']:16} "
            f"hit={r['hit']} miss={r['miss']} mode={r['compose_mode']} "
            f"plan={r['plan_source']} {r['timing_ms']}"
        )
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
