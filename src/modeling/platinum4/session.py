"""Conversation history for Platinum 4. The bot is a thread, not a one-shot note."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "session.v1"
MAX_TURNS = 12
EXCERPT = 480


def empty_session() -> dict[str, Any]:
    return {"schema_version": SCHEMA, "turns": [], "held": []}


def load_session(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_session()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return empty_session()
    data.setdefault("schema_version", SCHEMA)
    data.setdefault("turns", [])
    data.setdefault("held", [])
    return data


def save_session(session: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def held_unit_ids(session: dict[str, Any] | None) -> list[str]:
    ids: list[str] = []
    for row in (session or {}).get("held") or []:
        uid = row.get("unit_id") if isinstance(row, dict) else row
        if uid and uid not in ids:
            ids.append(uid)
    for turn in (session or {}).get("turns") or []:
        for uid in turn.get("unit_ids") or []:
            if uid not in ids:
                ids.append(uid)
    return ids


def held_catalog(session: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for row in (session or {}).get("held") or []:
        uid = row.get("unit_id")
        if uid and uid not in seen:
            seen.add(uid)
            rows.append(row)
    return rows


def history_for_model(session: dict[str, Any] | None, *, last_n: int = 6) -> list[dict[str, Any]]:
    turns = (session or {}).get("turns") or []
    out = []
    for t in turns[-last_n:]:
        out.append(
            {
                "question": t.get("question"),
                "shape": t.get("response_shape"),
                "cites": t.get("cites") or [],
                "unit_ids": t.get("unit_ids") or [],
                "excerpt": t.get("excerpt") or "",
            }
        )
    return out


def append_turn(
    session: dict[str, Any],
    *,
    question: str,
    packet: dict[str, Any],
    markdown: str,
    response_shape: str,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retrieved = packet.get("retrieved") or []
    unit_ids = [u.get("unit_id") for u in retrieved if u.get("unit_id")]
    cites = [u.get("cite") for u in retrieved if u.get("cite")]
    topics: list[str] = []
    held = list(session.get("held") or [])
    by_id = {h.get("unit_id"): h for h in held if h.get("unit_id")}
    for u in retrieved:
        uid = u.get("unit_id")
        tags = u.get("tags") or {}
        for t in tags.get("topic") or []:
            if t not in topics:
                topics.append(t)
        if uid:
            by_id[uid] = {
                "unit_id": uid,
                "cite": u.get("cite"),
                "title": u.get("title"),
                "topics": list(tags.get("topic") or []),
                "risk_code": list(tags.get("risk_code") or []),
            }
    excerpt = " ".join((markdown or "").split())[:EXCERPT]
    turn = {
        "question": question,
        "response_shape": response_shape,
        "unit_ids": unit_ids,
        "cites": cites,
        "topics": topics,
        "excerpt": excerpt,
        "need_search": (plan or {}).get("need_search"),
    }
    session.setdefault("turns", []).append(turn)
    session["turns"] = session["turns"][-MAX_TURNS:]
    session["held"] = list(by_id.values())[-40:]
    return session
