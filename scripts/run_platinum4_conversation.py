"""Five-turn Platinum 4 conversation: paragraph asks, two-track analysis, search vs reuse."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.conversation_cases import TURNS
from src.modeling.platinum4.pipeline import run_thread
from src.modeling.platinum4.session import empty_session, save_session


def _card(key: str) -> dict:
    cards = json.loads((REPO / "platinum3" / "results" / "sample_cards.json").read_text(encoding="utf-8"))
    for c in cards:
        if c.get("project_key") == key and (c.get("scenario") or {}).get("name") == "baseline":
            return c
    raise KeyError(key)


def _ids(result: dict) -> list[str]:
    return [u.get("unit_id") for u in (result["packet"].get("retrieved") or []) if u.get("unit_id")]


def _cite_block(md: str) -> str:
    m = re.search(r"## Citations\s*\n(.*?)(?:\n## |\nCompliance:|\Z)", md or "", re.S)
    return m.group(1) if m else ""


def score_thread(slim: list[dict], mds: list[str]) -> list[str]:
    """Code bars for the six live misses. Not an LLM pass."""
    misses: list[str] = []
    held: set[str] = set()
    for i, (row, md) in enumerate(zip(slim, mds), start=1):
        body = re.sub(r"## Citations[\s\S]*?(?=\n## |\nCompliance:|\Z)", "", md or "")
        cites = _cite_block(md)
        gip_rule = bool(re.search(r"pursuant to Section 3\.6", md, re.I))
        unused_neighbors = [
            sec
            for sec in ("6.1.5.1", "5.2.5", "5.3.5", "4.2 Initial")
            if sec in cites and sec not in body
        ]
        if i == 1:
            if re.search(r"BPM-015 r33 §7\.3", body) and "do not create" not in md.lower():
                misses.append("t1 cited §7.3 as a card-flag duty")
            if gip_rule:
                misses.append("t1 treated GIP 3.6 as a retrieved rule")
            if "bpm015-r33::5.4.6" not in (row.get("ids") or []):
                misses.append("t1 missed restudy §5.4.6")
        if i == 2:
            if row.get("searched"):
                misses.append("t2 searched instead of reuse")
            fund = re.findall(r"funds? the restudy[^.]+", md, re.I)
            if fund and "§4.2.4.5" in fund[0]:
                misses.append("t2 funded restudy from D2 §4.2.4.5")
        if i == 3:
            d2_lines = [ln for ln in md.splitlines() if re.search(r"\bD2\b", ln)]
            if any("§6.2.11" in ln and "M2" not in ln and "M3" not in ln for ln in d2_lines):
                misses.append("t3 put D2 at-risk onto §6.2.11")
            fund = re.findall(r"funds? the restudy[^.]+", md, re.I)
            if fund and "§4.2.4.5" in fund[0]:
                misses.append("t3 funded restudy from D2")
        if i == 5:
            if gip_rule:
                misses.append("t5 treated GIP 3.6 as a retrieved rule")
            if re.search(r"automatically voids the GIA", md, re.I) and "does not" not in md.lower():
                misses.append("t5 inferred GIA void")
            if "bpm015-r33::7.3" in held and row.get("searched"):
                misses.append("t5 searched after §7.3 was already held")
            if "not in this packet" not in md.lower():
                misses.append("t5 omitted GIP gap")
        if unused_neighbors:
            misses.append(f"t{i} citations listed unused neighbors {unused_neighbors}")
        gip_hits = len(re.findall(r"The GIP \(Attachment X\) is the tariff", md))
        if gip_hits > 1:
            misses.append(f"t{i} duplicated GIP gap")
        held.update(row.get("ids") or [])
    return misses


def main() -> int:
    card = _card("P::B::E291")
    queries = [
        {
            "question": str(t["question"]),
            "card": card,
            "requirements": {
                "audience": "analyst",
                "dialect": "auto",
                "need": list(t.get("need") or ["workflow", "citations", "do_not_claim"]),
                "max_units": 12,
            },
            "split": "val",
        }
        for t in TURNS
    ]
    sess = empty_session()
    rows = run_thread(queries, sess)
    slim = []
    chunks = []
    mds = []
    for i, (spec, r) in enumerate(zip(TURNS, rows), start=1):
        ids = _ids(r)
        md = (r.get("composed") or {}).get("markdown") or ""
        mds.append(md)
        q = str(spec["question"])
        slim.append(
            {
                "turn": i,
                "id": spec.get("id"),
                "question": q,
                "searched": r.get("searched"),
                "need_search": (r.get("plan") or {}).get("need_search"),
                "shape": (r.get("composed") or {}).get("shape"),
                "compose_mode": (r.get("composed") or {}).get("compose_mode"),
                "merged": bool((r["packet"].get("search_trace") or {}).get("merged_held")),
                "ids": ids,
                "invented_cites": (r.get("composed") or {}).get("invented_cites") or [],
                "plan_reason": (r.get("plan") or {}).get("reason"),
                "flags": [
                    p.get("flags")
                    for p in ((r.get("composed") or {}).get("passes") or [])
                    if p.get("name") == "code_postcheck"
                ],
            }
        )
        chunks.append(
            f"# Turn {i} ({spec.get('id')})\n\nQuestion:\n\n{q}\n\n"
            f"searched={r.get('searched')} shape={(r.get('composed') or {}).get('shape')}\n\n{md.strip()}\n"
        )
        print(
            f"t{i} searched={r.get('searched')!s:5} merge={slim[-1]['merged']!s:5} "
            f"shape={(r.get('composed') or {}).get('shape')} n={len(ids)} "
            f"ids={ids[:6]}"
        )
    dest = REPO / "platinum4" / "results" / "conversation_check.json"
    md_dest = REPO / "platinum4" / "results" / "answers" / "conversation_five_turns.md"
    misses = score_thread(slim, mds)
    dest.write_text(json.dumps({"turns": slim, "misses": misses}, indent=2, default=str), encoding="utf-8")
    md_dest.write_text("\n---\n\n".join(chunks), encoding="utf-8")
    save_session(sess, REPO / "platinum4" / "results" / "sessions" / "conversation_five_turns.json")
    print("wrote", dest)
    print("wrote", md_dest)
    if misses:
        print("misses:")
        for m in misses:
            print(" -", m)
        return 1
    print("score: strong (no live bars missed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
