"""Two-pass Platinum 4 turn: plan, then search-or-reuse, then write.

gpt-4.1 is called at most twice. Code post-check is not an LLM pass.
"""

from __future__ import annotations

from typing import Any

from src.modeling.platinum4.compose import compose, plan_query
from src.modeling.platinum4.errors import EMPTY_QUERY, TEST_SEALED, BotError
from src.modeling.platinum4.gold_stack import attach_gold_stack
from src.modeling.platinum4.search import packet_from_unit_ids, retrieve_for_query
from src.modeling.platinum4.session import (
    append_turn,
    empty_session,
    held_unit_ids,
    history_for_model,
)


def packet_for_turn(
    query: dict[str, Any],
    session: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Search, reuse held units, or merge a new search into thread history."""
    q = dict(query or {})
    searched = False
    held = held_unit_ids(session)
    if plan.get("need_search") or not held:
        packet = retrieve_for_query(q)
        searched = True
        if held:
            orig_trace = packet.get("search_trace") or {}
            orig_gaps = list(packet.get("gaps") or [])
            new_ids = [u.get("unit_id") for u in (packet.get("retrieved") or []) if u.get("unit_id")]
            new_only = [uid for uid in new_ids if uid not in held]
            head = new_only[:6]
            merged = list(dict.fromkeys(head + held + new_only))
            cap = min(16, max(len(merged), int((q.get("requirements") or {}).get("max_units") or 12)))
            cap = min(16, cap)
            if merged[:cap] != new_ids:
                packet = packet_from_unit_ids(merged[:cap], q, reason="merge_history")
                packet["search_trace"] = {
                    **orig_trace,
                    **(packet.get("search_trace") or {}),
                    "merged_held": True,
                }
                packet["gaps"] = list(dict.fromkeys(orig_gaps + list(packet.get("gaps") or [])))
    else:
        ids = list(plan.get("reuse_unit_ids") or held)
        packet = packet_from_unit_ids(ids, q, reason=str(plan.get("reason") or "history_reuse"))
        if not (packet.get("retrieved") or []):
            packet = retrieve_for_query(q)
            searched = True
            plan["need_search"] = True
            plan["reason"] = (plan.get("reason") or "") + " (reuse empty; searched)"
    packet["wants_diagram"] = bool(plan.get("want_diagram") or packet.get("wants_diagram"))
    return packet, searched


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
    attach_gold_stack(q)

    session = session or empty_session()
    req = dict(q.get("requirements") or {})
    dialect = req.get("dialect") or "auto"
    need_flags = list(req.get("need") or [])
    plan = plan_query(question, session, dialect=dialect, card=card, gold_stack=q.get("gold_stack"))
    mode = str(q.get("mode") or "").strip().lower()
    if mode == "chat":
        plan["mode"] = "chat"
        plan["response_shape"] = "short"
        plan["want_diagram"] = False
    elif mode == "reformat":
        plan["mode"] = "reformat"
        plan["need_search"] = False
        plan["reuse_unit_ids"] = held_unit_ids(session)
        if q.get("want_diagram") is False:
            plan["want_diagram"] = False
        elif q.get("want_diagram") is True:
            plan["want_diagram"] = True
    else:
        if q.get("want_diagram") is False:
            plan["want_diagram"] = False
        elif q.get("want_diagram") is True or "diagram" in need_flags:
            plan["want_diagram"] = True
            if "diagram" in need_flags and plan.get("response_shape") in {"short", "citation_brief"}:
                plan["response_shape"] = "diagram"
            elif q.get("want_diagram") is True and plan.get("response_shape") == "short" and not held_unit_ids(session):
                plan["response_shape"] = "standard"
    if dialect in {"bpm_register", "long", "short", "standard", "citation_brief"} and dialect != "auto":
        if dialect == "bpm_register":
            plan["response_shape"] = "long"
        else:
            plan["response_shape"] = dialect

    packet, searched = packet_for_turn(q, session, plan)
    attach_gold_stack(q, packet)
    pq = dict(packet.get("query") or {})
    if q.get("mode"):
        pq["mode"] = q.get("mode")
    if q.get("pinned_study"):
        pq["pinned_study"] = q.get("pinned_study")
    packet["query"] = pq
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


def run_thread(
    queries: list[dict[str, Any]],
    session: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run two or more turns on one session so history, reuse, and merge can be scored."""
    session = session or empty_session()
    rows = []
    for q in queries:
        rows.append(run_turn(q, session))
    return rows
