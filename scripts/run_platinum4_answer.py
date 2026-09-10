#!/usr/bin/env python3
"""Compose a BPM-015 procedure note (plan + write). Conversation is stored in a session.

  python scripts/run_platinum4_answer.py --question "Who funds a restudy if a peer withdraws?" --project-key P::B::E291
  python scripts/run_platinum4_answer.py --question "Who pays for that?" --session platinum4/results/sessions/default.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.compose import PINNED_MODEL
from src.modeling.platinum4.dialect import sample_zero_hits
from src.modeling.platinum4.errors import (
    EMPTY_QUERY,
    INDEX_MISSING,
    TEST_SEALED,
    BotError,
)
from src.modeling.platinum4.pipeline import run_turn
from src.modeling.platinum4.session import load_session, save_session, empty_session

SAMPLE_KEYS = ("P::B::E291", "P::J2280", "P::J2460")
ANSWERS = REPO / "platinum4" / "results" / "answers"
DEFAULT_SESSION = REPO / "platinum4" / "results" / "sessions" / "default.json"


def _slug(question: str, project_key: str | None) -> str:
    q = re.sub(r"[^a-z0-9]+", "-", (question or "query").lower()).strip("-")[:48] or "query"
    key = (project_key or "q").replace(":", "")
    return f"{key}_{q}"


def _load_card(project_key: str, scenario: str) -> dict:
    path = REPO / "platinum3" / "results" / "sample_cards.json"
    if not path.exists():
        raise SystemExit(f"missing {path}; run python scripts/run_platinum3_risk_cards.py")
    cards = json.loads(path.read_text(encoding="utf-8"))
    for c in cards:
        if c.get("project_key") == project_key and (c.get("scenario") or {}).get("name") == scenario:
            return c
    for c in cards:
        if c.get("project_key") == project_key:
            return c
    raise SystemExit(f"no sample card for {project_key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Platinum 4 gpt-4.1 procedure note (plan + write)")
    parser.add_argument("--question", default="", help="Free-text question")
    parser.add_argument("--project-key", default="", help="One of the three val sample keys")
    parser.add_argument("--scenario", default="baseline")
    parser.add_argument(
        "--dialect",
        default="auto",
        choices=("auto", "short", "standard", "long", "bpm_register", "citation_brief"),
        help="auto lets the planner pick short/standard/long",
    )
    parser.add_argument("--need", nargs="*", default=None, help="Need flags, e.g. diagram")
    parser.add_argument("--split", default="val")
    parser.add_argument("--audience", default="analyst")
    parser.add_argument("--session", default=str(DEFAULT_SESSION), help="Conversation JSON (history)")
    parser.add_argument("--reset-session", action="store_true")
    args = parser.parse_args()

    if args.split == "test":
        print("REFUSED: test is sealed.", flush=True)
        return 2
    question = (args.question or "").strip()
    project_key = (args.project_key or "").strip() or None
    if project_key and project_key not in SAMPLE_KEYS:
        print(
            f"REFUSED: only sample projects {', '.join(SAMPLE_KEYS)} are allowed in this pass.",
            flush=True,
        )
        return 2
    card = _load_card(project_key, args.scenario) if project_key else None
    need = ["workflow", "stakeholders", "citations", "do_not_claim"]
    for extra in args.need or []:
        if extra not in need:
            need.append(extra)
    query = {
        "question": question,
        "card": card,
        "requirements": {
            "audience": args.audience,
            "dialect": args.dialect,
            "need": need,
            "max_units": 12,
        },
        "split": args.split,
    }
    session_path = Path(args.session)
    session = empty_session() if args.reset_session else load_session(session_path)
    slug = _slug(question, project_key)
    dest_md = ANSWERS / f"{slug}.md"
    dest_json = ANSWERS / f"{slug}.json"
    ANSWERS.mkdir(parents=True, exist_ok=True)
    try:
        result = run_turn(query, session)
    except BotError as exc:
        md = sample_zero_hits()
        payload = {
            "error_code": exc.code,
            "message": str(exc),
            "model": PINNED_MODEL,
            "markdown": md,
        }
        dest_md.write_text(md, encoding="utf-8")
        dest_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(md)
        print(f"wrote {dest_md}", flush=True)
        if exc.code in {EMPTY_QUERY, INDEX_MISSING, TEST_SEALED}:
            return 2
        return 0

    composed = result["composed"]
    packet = result["packet"]
    md = composed.get("markdown") or sample_zero_hits()
    sidecar = {
        "model": PINNED_MODEL,
        "dialect": args.dialect,
        "shape": composed.get("shape"),
        "question": question,
        "project_key": project_key,
        "searched": result.get("searched"),
        "plan": result.get("plan"),
        "packet": packet,
        "search_trace": packet.get("search_trace"),
        "graph_slice": packet.get("graph_slice"),
        "passes": composed.get("passes"),
        "compose_mode": composed.get("compose_mode"),
        "error_code": composed.get("error_code") or packet.get("error_code"),
        "ok": composed.get("ok"),
        "n_history_turns": len((result.get("session") or {}).get("turns") or []),
    }
    dest_md.write_text(md, encoding="utf-8")
    dest_json.write_text(json.dumps(sidecar, indent=2, default=str), encoding="utf-8")
    save_session(result["session"], session_path)
    print(md)
    print(f"wrote {dest_md}", flush=True)
    print(f"wrote {dest_json}", flush=True)
    print(f"session {session_path} searched={result.get('searched')} shape={composed.get('shape')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
