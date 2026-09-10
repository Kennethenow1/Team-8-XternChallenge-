"""Two-pass Platinum 4 turn: plan, then search-or-reuse, then write.

gpt-4.1 is called at most twice. Code post-check is not an LLM pass.
"""

from __future__ import annotations

from typing import Any

from src.modeling.platinum4.compose import compose, plan_query
from src.modeling.platinum4.errors import EMPTY_QUERY, TEST_SEALED, BotError
from src.modeling.platinum4.search import packet_from_unit_ids, retrieve_for_query
from src.modeling.platinum4.session import (
    append_turn,
    empty_session,
    held_unit_ids,
    history_for_model,
)


def run_turn(
    query: dict[str, Any] | None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = dict(query or {})
    question = str(q.get("question") or "").strip()
    card = q.get("card")
    if isinstance(card, dict) and not card:
        card = None
        q["card"] = None
    if q.get("split") == "test":
        raise BotError(TEST_SEALED, "2024 test is sealed. Do not retrieve for split=test.")
    if not question and not card:
        raise BotError(EMPTY_QUERY, "No question and no card. Abort.")

    session = session or empty_session()
    req = dict(q.get("requirements") or {})
    dialect = req.get("dialect") or "auto"
    need_flags = list(req.get("need") or [])
    plan = plan_query(question, session, dialect=dialect, card=card)
    if "diagram" in need_flags:
        plan["want_diagram"] = True
        if plan.get("response_shape") in {"short", "citation_brief"}:
            plan["response_shape"] = "diagram"
    if dialect in {"bpm_register", "long", "short", "standard", "citation_brief"} and dialect != "auto":
        if dialect == "bpm_register":
            plan["response_shape"] = "long"
        else:
            plan["response_shape"] = dialect

    searched = False
    if plan.get("need_search") or not held_unit_ids(session):
        packet = retrieve_for_query(q)
        searched = True
    else:
        ids = list(plan.get("reuse_unit_ids") or held_unit_ids(session))
        packet = packet_from_unit_ids(ids, q, reason=str(plan.get("reason") or "history_reuse"))
        if not (packet.get("retrieved") or []):
            packet = retrieve_for_query(q)
            searched = True
            plan["need_search"] = True
            plan["reason"] = (plan.get("reason") or "") + " (reuse empty; searched)"

    packet["wants_diagram"] = bool(plan.get("want_diagram") or packet.get("wants_diagram"))
    composed = compose(
        packet,
        dialect=dialect,
        shape=plan.get("response_shape"),
        history=history_for_model(session),
        plan=plan,
    )
    append_turn(
        session,
        question=question,
        packet=packet,
        markdown=composed.get("markdown") or "",
        response_shape=composed.get("shape") or plan.get("response_shape") or "standard",
        plan=plan,
    )
    return {
        "packet": packet,
        "composed": composed,
        "plan": plan,
        "session": session,
        "searched": searched,
    }
