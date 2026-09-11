"""Ask gpt-4.1 to critique Platinum 4 notes against the retrieved packet.

Not a pipeline pass. Does not repair drafts. Does not unseal 2024.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.compose import PINNED_MODEL, _chat
from src.modeling.platinum4.errors import BotError

OUT_JSON = REPO / "platinum4" / "results" / "gpt_response_analysis.json"
OUT_MD = REPO / "platinum4" / "results" / "gpt_response_analysis.md"


SYSTEM = """You are reviewing a MISO BPM-015 r33 procedure bot. Pinned model is gpt-4.1.
Judge only whether each note restates the retrieved packet. Return JSON only.
Keys:
- overall_verdict: pass | mixed | fail
- overall: 4-8 sentences
- notes: list of objects with keys name, verdict (pass|mixed|fail), restates_packet (bool),
  overclaims (list of strings), honesty_gaps (list of strings), followup_ok (bool or null),
  comment (2-5 sentences)
Rules:
- A cite is invented if it is not in retrieved_cites for that turn.
- Stub risks (developer serial quit, FEMA, IRA energy-community) have no BPM-015 clause. The note must say so.
- GIP / Attachment X / GIP section 3.6 are not in the packet. The note must not treat them as retrieved BPM.
- Do not invent BPM to fill holes. If the note infers that a GIA is void after a restudy no-response, flag it unless the packet says that.
- Compliance must stay not_determined.
- Do not mention 2024 test labels or y_true.
- Follow-up should be shorter and should not search-invent GIP section text.
"""


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _md(path: Path, cap: int = 6000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) > cap:
        return text[:cap].rstrip() + "\n..."
    return text


def payload() -> dict:
    sample = _load_json(REPO / "platinum4" / "results" / "sample_check.json")
    mix = _load_json(REPO / "platinum4" / "results" / "complex_mix_check.json")
    sess = _load_json(REPO / "platinum4" / "results" / "sessions" / "sample_check.json")
    mix_sess = _load_json(REPO / "platinum4" / "results" / "sessions" / "complex_mix.json")
    answers = {
        "complex_mix": _md(REPO / "platinum4" / "results" / "answers" / "complex_mix.md", 9000),
        "restudy": _md(REPO / "platinum4" / "results" / "answers" / "PBE291_who-funds-a-restudy-if-a-peer-withdraws.md"),
        "followup_days": _md(
            REPO / "platinum4" / "results" / "answers" / "q_who-pays-for-that-and-how-many-business-days-doe.md"
        ),
        "dp2": _md(REPO / "platinum4" / "results" / "answers" / "PJ2280_what-happens-at-decision-point-ii.md"),
        "sample_check_notes": _md(REPO / "platinum4" / "results" / "answers" / "sample_check_notes.md", 9000),
        "sample_session_excerpts": [
            {
                "question": t.get("question"),
                "shape": t.get("response_shape"),
                "cites": t.get("cites"),
                "excerpt": t.get("excerpt"),
            }
            for t in (sess.get("turns") or [])
        ],
        "mix_session_cites": [
            {
                "question": (t.get("question") or "")[:240],
                "shape": t.get("response_shape"),
                "cites": t.get("cites"),
                "need_search": t.get("need_search"),
                "excerpt": t.get("excerpt"),
            }
            for t in (mix_sess.get("turns") or [])
        ],
    }
    sample_rows = []
    for r in sample.get("rows") or []:
        sample_rows.append(
            {
                "name": r.get("name"),
                "question": r.get("question"),
                "searched": r.get("searched"),
                "shape": r.get("shape"),
                "compose_mode": r.get("compose_mode"),
                "hit": r.get("hit"),
                "miss": r.get("miss"),
                "invented_cites": r.get("invented_cites"),
                "error_code": r.get("error_code"),
                "excerpt": r.get("excerpt"),
                "plan_reason": r.get("plan_reason"),
            }
        )
    mix_rows = []
    for r in mix.get("rows") or []:
        mix_rows.append(
            {
                "name": r.get("name"),
                "searched": r.get("searched"),
                "shape": r.get("shape"),
                "compose_mode": r.get("compose_mode"),
                "ids": r.get("ids"),
                "hits": r.get("hits"),
                "miss": r.get("miss"),
                "has_mermaid": r.get("has_mermaid"),
                "gip_gap": r.get("gip_gap"),
                "stub_honest": r.get("stub_honest"),
                "invented_cites": r.get("invented_cites"),
                "plan_reason": r.get("plan_reason"),
            }
        )
    return {
        "model_required": PINNED_MODEL,
        "code_score_sample": sample_rows,
        "code_score_mix": mix_rows,
        "notes_markdown": answers,
        "known_failure_modes": [
            "family cap dropped D2 4.2.4.5 and 6.2.11 in favor of 4.2 / 4.2.4.6 / 6.2.7-9",
            "template ## Workflow title-dump after Citations on numbered long notes",
            "follow-up inferred GIA void and §7.3 inapplicable after restudy no-response, without GIP in packet",
            "restudy funding cited to parent §4.2 instead of remaining-deposit / D2 language",
        ],
    }


def to_markdown(parsed: dict, meta: dict) -> str:
    lines = [
        "# gpt-4.1 review of Platinum 4 notes",
        "",
        f"Model: `{parsed.get('model') or PINNED_MODEL}`. This is a review of already-written notes, not a third pipeline pass.",
        "",
        f"**Verdict:** {parsed.get('overall_verdict') or 'unknown'}",
        "",
        parsed.get("overall") or "",
        "",
        "## Per note",
        "",
    ]
    for row in parsed.get("notes") or []:
        lines.append(f"### {row.get('name')}")
        lines.append("")
        lines.append(
            f"- verdict: **{row.get('verdict')}**; restates packet: {row.get('restates_packet')}; "
            f"follow-up ok: {row.get('followup_ok')}"
        )
        over = row.get("overclaims") or []
        if over:
            lines.append("- overclaims:")
            for item in over:
                lines.append(f"  - {item}")
        gaps = row.get("honesty_gaps") or []
        if gaps:
            lines.append("- honesty gaps:")
            for item in gaps:
                lines.append(f"  - {item}")
        if row.get("comment"):
            lines.append(f"- {row.get('comment')}")
        lines.append("")
    usage = meta.get("usage") or {}
    if usage:
        lines.append("## Usage")
        lines.append("")
        lines.append(
            f"prompt_tokens={usage.get('prompt_tokens')} "
            f"completion_tokens={usage.get('completion_tokens')} "
            f"total_tokens={usage.get('total_tokens')}"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    body = payload()
    if not (body["code_score_sample"] or body["code_score_mix"] or any(body["notes_markdown"].values())):
        print("no Platinum 4 results to review; run sample_check / complex_mix first")
        return 1
    try:
        raw, meta = _chat(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(body, ensure_ascii=False)},
            ],
            json_mode=True,
        )
    except BotError as exc:
        print(f"{exc.code}: {exc}")
        return 1
    parsed = json.loads(raw)
    parsed["model"] = meta.get("model") or PINNED_MODEL
    OUT_JSON.write_text(json.dumps({"review": parsed, "meta": meta}, indent=2, default=str), encoding="utf-8")
    OUT_MD.write_text(to_markdown(parsed, meta), encoding="utf-8")
    print(f"verdict={parsed.get('overall_verdict')} model={parsed.get('model')}")
    print(parsed.get("overall") or "")
    for row in parsed.get("notes") or []:
        print(f"  {row.get('name')}: {row.get('verdict')} restates={row.get('restates_packet')}")
    print("wrote", OUT_JSON)
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
