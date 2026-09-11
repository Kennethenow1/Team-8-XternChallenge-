"""Load a full-stack JSON (CatBoost + Platinum 2 + Platinum 3) and run the conversation.

  python scripts/run_platinum4_full_stack.py
  python scripts/run_platinum4_full_stack.py --input platinum4/results/fixtures/full_stack_input.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.gold_stack import (
    DEFAULT_FIXTURE,
    gold_stack_for_model,
    load_full_stack_input,
    queries_from_full_stack,
)
from src.modeling.platinum4.pipeline import run_thread
from src.modeling.platinum4.session import empty_session, save_session


def _scoreboard_md(resolved: dict) -> str:
    stack = resolved.get("gold_stack") or {}
    cb = stack.get("catboost") or {}
    p2 = stack.get("platinum2") or {}
    p3 = stack.get("platinum3") or {}
    proj = stack.get("project") or {}
    bpm = ", ".join(r.get("code") or "" for r in (p3.get("risks_bpm") or [])) or "(none)"
    stubs = ", ".join(r.get("code") or "" for r in (p3.get("risks_stub") or [])) or "(none)"
    lines = [
        "# Full-stack demo: CatBoost + Platinum 2 + Platinum 3",
        "",
        "Quit scores are **CatBoost** (`catboost_tuned` / trial-149). Not Electrum. "
        "Not Platinum 1 delay-months. 2024 stays sealed.",
        "",
        "## Scoreboard (code, not gpt-4.1)",
        "",
        f"| Slot | Value | Honest use |",
        f"|------|-------|------------|",
        f"| Project | `{proj.get('project_key')}` · {proj.get('study_phase')} · "
        f"{proj.get('capacity_mw')} MW · {proj.get('observation_date')} | Val sample only |",
        f"| Scenario | `{p3.get('scenario')}` | {p3.get('scenario_note')} |",
        f"| CatBoost P(quit 12m) | {cb.get('p_quit_12m')} | Ranking, not a BPM trigger |",
        f"| CatBoost under scenario | {cb.get('p_quit_under_scenario')} "
        f"(delta {cb.get('delta_p_quit')}) | Sensitivity, not causal |",
        f"| Platinum 2 delayed MW now | {p2.get('delayed_mw_now')} | EIA planned pile |",
        f"| Platinum 2 Holt 3m / 12m | {p2.get('delayed_mw_h3')} / {p2.get('delayed_mw_h12')} | "
        f"History ≤ as-of; not 2024 actuals |",
        f"| GIA-matched delayed MW | {p2.get('gia_delayed_mw_now')} | Thin overlay |",
        f"| Risks with BPM index | {bpm} | Procedure units may exist |",
        f"| Stub risks | {stubs} | Gaps only; no invented BPM |",
        "",
        "## Input",
        "",
        f"Fixture `{DEFAULT_FIXTURE.relative_to(REPO)}` loaded `{resolved.get('dataset')}`.",
        "",
    ]
    return "\n".join(lines)


def _ids(result: dict) -> list[str]:
    return [u.get("unit_id") for u in (result["packet"].get("retrieved") or []) if u.get("unit_id")]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Platinum 4 full-stack conversation")
    parser.add_argument("--input", default=str(DEFAULT_FIXTURE))
    args = parser.parse_args()
    resolved = load_full_stack_input(Path(args.input))
    queries = queries_from_full_stack(resolved)
    if not queries:
        print("no conversation turns in input", flush=True)
        return 2
    dest_dir = REPO / "platinum4" / "results"
    answers = dest_dir / "answers"
    dest_dir.mkdir(parents=True, exist_ok=True)
    answers.mkdir(parents=True, exist_ok=True)
    resolved_path = dest_dir / "full_stack_resolved.json"
    slim_resolved = {
        "schema_version": resolved.get("schema_version"),
        "split": resolved.get("split"),
        "project_key": resolved.get("project_key"),
        "scenario": resolved.get("scenario"),
        "gold_stack": gold_stack_for_model(resolved.get("gold_stack")),
        "conversation": [
            {"id": t.get("id"), "question": t.get("question")}
            for t in (resolved.get("conversation") or [])
        ],
    }
    resolved_path.write_text(json.dumps(slim_resolved, indent=2, default=str), encoding="utf-8")

    sess = empty_session()
    rows = run_thread(queries, sess)
    chunks = [_scoreboard_md(resolved)]
    slim = []
    for i, (spec, r) in enumerate(zip(resolved.get("conversation") or [], rows), start=1):
        md = (r.get("composed") or {}).get("markdown") or ""
        ids = _ids(r)
        slim.append(
            {
                "turn": i,
                "id": spec.get("id"),
                "searched": r.get("searched"),
                "shape": (r.get("composed") or {}).get("shape"),
                "ids": ids,
                "invented_cites": (r.get("composed") or {}).get("invented_cites") or [],
            }
        )
        chunks.append(
            f"## Turn {i} ({spec.get('id')})\n\n"
            f"searched={r.get('searched')} shape={(r.get('composed') or {}).get('shape')}\n\n"
            f"{md.strip()}\n"
        )
        print(
            f"t{i} searched={r.get('searched')!s:5} "
            f"shape={(r.get('composed') or {}).get('shape')} n={len(ids)} ids={ids[:6]}",
            flush=True,
        )
    md_dest = answers / "full_stack_conversation.md"
    json_dest = dest_dir / "full_stack_check.json"
    md_dest.write_text("\n---\n\n".join(chunks), encoding="utf-8")
    json_dest.write_text(json.dumps({"turns": slim}, indent=2, default=str), encoding="utf-8")
    save_session(sess, dest_dir / "sessions" / "full_stack.json")
    print("wrote", resolved_path, flush=True)
    print("wrote", md_dest, flush=True)
    print("wrote", json_dest, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
