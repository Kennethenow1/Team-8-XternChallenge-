"""Retrieval-first complex checks for Platinum 4. No GPT required."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.modeling.platinum4.compose import heuristic_plan, post_check
from src.modeling.platinum4.conversation_cases import questions as conversation_questions
from src.modeling.platinum4.errors import EMPTY_QUERY, TEST_SEALED, BotError
from src.modeling.platinum4.search import retrieve_for_query, packet_from_unit_ids
from src.modeling.platinum4.session import append_turn, empty_session

REPO = Path(__file__).resolve().parents[1]
CARDS = REPO / "platinum3" / "results" / "sample_cards.json"

UID = {
    "restudy": "bpm015-r33::5.4.6",
    "dp2": "bpm015-r33::5.3.3",
    "d2": "bpm015-r33::4.2.4.5",
    "cod_delay": "bpm015-r33::7.3",
    "cod": "bpm015-r33::7.7",
    "m3m4": "bpm015-r33::6.2.11",
    "site": "bpm015-r33::5.1.2",
    "suspension": "bpm015-r33::7.1",
}


def _card(key: str) -> dict:
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    for c in cards:
        if c.get("project_key") == key and (c.get("scenario") or {}).get("name") == "baseline":
            return c
    raise KeyError(key)


def _ids(packet: dict) -> list[str]:
    return [u.get("unit_id") for u in (packet.get("retrieved") or []) if u.get("unit_id")]


def _gaps(packet: dict) -> str:
    return " ".join(str(g) for g in (packet.get("gaps") or [])).lower()


def _session_holding(unit_ids: list[str], question: str = "restudy notice window") -> dict:
    sess = empty_session()
    packet = packet_from_unit_ids(unit_ids, {"question": question})
    append_turn(
        sess,
        question=question,
        packet=packet,
        markdown="held",
        response_shape="standard",
        plan={"need_search": True},
    )
    return sess


def test_01_mix_restudy_gia_cod_d2_dp_stubs_gip():
    q = (
        "Walk through restudy after a peer IR withdrew, post-GIA COD delay now that the "
        "interconnection agreement is executed and COD has passed, Decision Point II "
        "withdrawal of M3/M4 milestone deposits and the D2 study funding deposit, plus "
        "developer serial quit, FEMA hazard, and IRA energy-community. If you need the GIP "
        "or Attachment X, put that under Gaps. Use only BPM-015 r33."
    )
    packet = retrieve_for_query(
        {
            "question": q,
            "card": _card("P::B::E291"),
            "requirements": {"max_units": 12},
            "split": "val",
        }
    )
    ids = _ids(packet)
    must = [UID["restudy"], UID["cod_delay"], UID["cod"], UID["d2"], UID["dp2"]]
    missing = [u for u in must if u not in ids]
    assert not missing, f"missing {missing}; got {ids}"
    assert all("r32" not in i and "redline" not in i for i in ids)
    gaps = _gaps(packet)
    assert "gip" in gaps or "attachment x" in gaps
    assert "no bpm-015 clause" in gaps or "stub" in gaps


def test_02_restudy_gip_deemed_withdrawal():
    packet = retrieve_for_query(
        {
            "question": (
                "If the IC misses the restudy notice, is the IR deemed withdrawn under "
                "Section 3.6 of the GIP?"
            )
        }
    )
    ids = _ids(packet)
    assert UID["restudy"] in ids, ids
    gaps = _gaps(packet)
    assert "gip" in gaps or "attachment x" in gaps


def test_03_j2280_sis_dp_d2_milestones():
    packet = retrieve_for_query(
        {
            "question": (
                "This IR is in System Impact Study. At Decision Point II, what happens to "
                "DPP milestone deposits M3 and M4 and the D2 study funding deposit?"
            ),
            "card": _card("P::J2280"),
            "split": "val",
        }
    )
    ids = _ids(packet)
    must = [UID["dp2"], UID["d2"], UID["m3m4"]]
    missing = [u for u in must if u not in ids]
    assert not missing, f"missing {missing}; got {ids}"
    assert all("r32" not in i for i in ids)


def test_04_j2460_not_started_site_control_d2():
    packet = retrieve_for_query(
        {
            "question": (
                "IR is Not Started. What are the site control rules and the D2 study "
                "funding deposit? FEMA and IRA energy-community are on the card."
            ),
            "card": _card("P::J2460"),
            "split": "val",
        }
    )
    ids = _ids(packet)
    must = [UID["site"], UID["d2"]]
    missing = [u for u in must if u not in ids]
    assert not missing, f"missing {missing}; got {ids}"
    gaps = _gaps(packet)
    assert "no bpm-015 clause" in gaps or "hazard" in gaps or "policy_incentive" in gaps or "fema" in gaps


def test_05_contour_congestion_restudy():
    packet = retrieve_for_query(
        {
            "question": (
                "How does contour grouping and congestion interact with a restudy after "
                "a withdrawal in the same DPP cycle?"
            )
        }
    )
    ids = _ids(packet)
    assert UID["restudy"] in ids, ids
    tags = []
    for u in packet.get("retrieved") or []:
        tags.extend((u.get("tags") or {}).get("topic") or [])
    assert "scoping" in tags or any("4.3" in i or "3.1.1" in i for i in ids), ids


def test_06_suspension_cod_post_gia():
    packet = retrieve_for_query(
        {
            "question": (
                "After GIA execution, can the IC suspend construction, and which "
                "commercial operation / COD delay clauses apply?"
            )
        }
    )
    ids = _ids(packet)
    must = [UID["suspension"], UID["cod_delay"], UID["cod"]]
    missing = [u for u in must if u not in ids]
    assert not missing, f"missing {missing}; got {ids}"


def test_07_letter_of_credit_restudy_funding():
    packet = retrieve_for_query(
        {
            "question": (
                "Who posts the letter of credit for the restudy, and what is the D2 "
                "study funding deposit?"
            )
        }
    )
    ids = _ids(packet)
    must = [UID["restudy"], UID["d2"]]
    missing = [u for u in must if u not in ids]
    assert not missing, f"missing {missing}; got {ids}"


def test_08_followup_reuse_business_days():
    sess = _session_holding([UID["restudy"]], "restudy notice after a peer withdrawal")
    plan = heuristic_plan("How many Business Days does the IC have to respond?", sess)
    assert plan["need_search"] is False
    assert UID["restudy"] in (plan.get("reuse_unit_ids") or [])
    packet = packet_from_unit_ids(plan["reuse_unit_ids"], {"question": "How many Business Days?"})
    assert UID["restudy"] in _ids(packet)


def test_09_followup_new_topic_d2_searches():
    sess = _session_holding([UID["restudy"]], "restudy notice after a peer withdrawal")
    plan = heuristic_plan("What about the D2 study funding deposit?", sess)
    assert plan["need_search"] is True
    packet = retrieve_for_query({"question": "What about the D2 study funding deposit?"})
    assert UID["d2"] in _ids(packet)


def test_10_empty_query_sealed_postcheck_no_r32():
    with pytest.raises(BotError) as empty:
        retrieve_for_query({})
    assert empty.value.code == EMPTY_QUERY
    with pytest.raises(BotError) as sealed:
        retrieve_for_query({"question": "restudy", "split": "test"})
    assert sealed.value.code == TEST_SEALED

    md = (
        "# Interconnection procedure note\n\n"
        "## Situation\nThe IR is in restudy after a peer withdrawal. This is not a legal opinion.\n\n"
        "## 1. Restudy\nBPM-015 r33 §5.4.6 sets the restudy notice path.\n\n"
        "## Citations\n- BPM-015 r33 §5.4.6 - Restudy\n\n"
        "Compliance: not_determined.\n"
    )
    packet = {
        "retrieved": [
            {
                "unit_id": UID["restudy"],
                "cite": "BPM-015 r33 §5.4.6",
                "title": "Restudy",
                "pages": [1, 2],
            }
        ],
        "gaps": [],
        "do_not_claim": ["do not unseal 2024 test"],
    }
    out, _flags, invented = post_check(md, packet, dialect="bpm_register", shape="long")
    assert not invented
    assert "Compliance: not_determined" in out
    if "## Workflow" in out:
        after_cite = out.split("## Citations", 1)[-1]
        assert "## Workflow" not in after_cite
    assert "addresses Restudy" not in out

    packet = retrieve_for_query({"question": "restudy after a withdrawal"})
    ids = _ids(packet)
    assert ids
    assert all("r32" not in i and "redline" not in i for i in ids)
    assert UID["restudy"] in ids


def _play_thread(questions: list[str], card: dict | None = None) -> list[dict]:
    from src.modeling.platinum4.pipeline import packet_for_turn

    sess = empty_session()
    rows = []
    for q in questions:
        plan = heuristic_plan(q, sess)
        query = {
            "question": q,
            "card": card,
            "requirements": {"max_units": 12},
            "split": "val",
        }
        packet, searched = packet_for_turn(query, sess, plan)
        ids = _ids(packet)
        append_turn(
            sess,
            question=q,
            packet=packet,
            markdown="held " + q,
            response_shape=str(plan.get("response_shape") or "standard"),
            plan=plan,
        )
        rows.append(
            {
                "question": q,
                "searched": searched,
                "need_search": plan.get("need_search"),
                "ids": ids,
                "merged": bool((packet.get("search_trace") or {}).get("merged_held")),
                "gaps": packet.get("gaps") or [],
                "held_n": len(sess.get("held") or []),
            }
        )
    return rows


def test_11_conversation_five_turns_search_reuse_merge():
    """Paragraph thread: card+BPM, reuse clock, D2 vs restudy, site-control overlay, GIP vs §7.3."""
    card = _card("P::B::E291")
    questions = conversation_questions()
    rows = _play_thread(questions, card)
    assert len(rows) == 5
    t1, t2, t3, t4, t5 = rows
    p1 = heuristic_plan(questions[0], empty_session())
    assert p1["response_shape"] in {"long", "diagram"}
    p4 = heuristic_plan(questions[3], empty_session())
    assert p4["response_shape"] == "diagram"

    assert t1["searched"] is True
    assert UID["restudy"] in t1["ids"]

    assert t2["searched"] is False
    assert t2["need_search"] is False
    assert UID["restudy"] in t2["ids"]

    assert UID["d2"] in t3["ids"]
    assert UID["restudy"] in t3["ids"]
    if UID["d2"] in t1["ids"]:
        assert t3["searched"] is False
    else:
        assert t3["searched"] is True
        assert t3["merged"] is True

    assert t4["searched"] is True
    assert UID["site"] in t4["ids"]
    assert UID["restudy"] in t4["ids"]
    assert t4["merged"] is True

    assert UID["restudy"] in t5["ids"]
    assert UID["cod_delay"] in t5["ids"]
    held_before_t5 = set(t1["ids"]) | set(t2["ids"]) | set(t3["ids"]) | set(t4["ids"])
    if UID["cod_delay"] in held_before_t5:
        assert t5["searched"] is False
    else:
        assert t5["searched"] is True
    gaps = " ".join(str(g) for g in t5["gaps"]).lower()
    assert "gip" in gaps or "attachment x" in gaps
    assert all("r32" not in i and "redline" not in i for r in rows for i in r["ids"])


def test_12_postcheck_forces_packet_cites_and_blocks_gia_void():
    packet = {
        "query": {
            "question": (
                "If they miss the restudy window, is the IR deemed withdrawn under the GIP, "
                "and does section 7.3 still apply?"
            )
        },
        "retrieved": [
            {
                "unit_id": UID["restudy"],
                "cite": "BPM-015 r33 §5.4.6",
                "title": "Interconnection Study Restudy",
                "pages": [56, 56],
            },
            {
                "unit_id": UID["cod_delay"],
                "cite": "BPM-015 r33 §7.3",
                "title": "Interconnection Customer delays",
                "pages": [128, 129],
            },
        ],
        "gaps": ["The GIP (Attachment X) is the tariff and is not in this packet."],
        "do_not_claim": ["do not unseal 2024 test"],
    }
    md = (
        "If the IC misses the window the IR is deemed withdrawn (BPM-015 r33 §5.4.6). "
        "The GIA would no longer be in effect for that project, so section 7.3 would not apply.\n\n"
        "## Citations\n- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)\n\n"
        "Compliance: not_determined.\n"
    )
    out, flags, invented = post_check(md, packet, dialect="auto", shape="short")
    assert not invented
    assert "BPM-015 r33 §7.3" in out
    assert "Interconnection Customer delays" in out
    assert "no longer be in effect" not in out.lower() or "does not say that an already-executed GIA" in out
    assert "gia_termination_inferred" in flags
    assert "does not say that an already-executed GIA is terminated" in out
    assert "not in this packet" in out.lower()


def test_13_postcheck_gip_d2_and_used_cites():
    packet = {
        "query": {"question": "D2 vs restudy; GIP 3.6?"},
        "retrieved": [
            {
                "unit_id": UID["restudy"],
                "cite": "BPM-015 r33 §5.4.6",
                "title": "Interconnection Study Restudy",
                "bpm_section": "5.4.6",
                "pages": [56, 56],
            },
            {
                "unit_id": UID["d2"],
                "cite": "BPM-015 r33 §4.2.4.5",
                "title": "DPP Study Funding Deposit (D2)",
                "bpm_section": "4.2.4.5",
                "pages": [33, 34],
            },
            {
                "unit_id": "bpm015-r33::6.1.5.1",
                "cite": "BPM-015 r33 §6.1.5.1",
                "title": "Background",
                "bpm_section": "6.1.5.1",
                "pages": [79, 79],
            },
            {
                "unit_id": "bpm015-r33::4.2",
                "cite": "BPM-015 r33 §4.2",
                "title": "Initial Screening",
                "bpm_section": "4.2",
                "pages": [26, 27],
            },
        ],
        "gaps": [
            "The GIP (Attachment X) is the tariff and is not in this packet.",
            "developer_serial_quit has no BPM-015 clause",
            "No BPM-015 clause was retrieved for developer serial quit.",
            "no unit kept for lexicon risk system_congestion",
        ],
        "do_not_claim": ["do not unseal 2024 test"],
    }
    md = (
        "The IC funds the restudy from remaining deposit (BPM-015 r33 §4.2.4.5). "
        "D2 is at risk after Decision Point I (BPM-015 r33 §6.2.11). "
        "Silence is deemed withdrawn pursuant to Section 3.6 of the GIP (BPM-015 r33 §5.4.6).\n\n"
        "Compliance: not_determined.\n"
    )
    out, _flags, invented = post_check(md, packet, dialect="auto", shape="long")
    assert not invented
    assert "pursuant to Section 3.6" not in out
    assert "not in this packet" in out.lower()
    assert "funds the restudy" in out
    assert "§4.2.4.5" not in re.findall(r"funds the restudy[^.]+", out)[0]
    assert "D2 is at risk" in out
    assert "§6.2.11" not in [ln for ln in out.splitlines() if "D2 is at risk" in ln][0]
    assert "§6.1.5.1" not in out
    assert "§4.2 - Initial" not in out
    assert out.lower().count("developer_serial_quit has no bpm-015 clause") == 1
    assert "system_congestion" not in out.lower()


def test_14_card_context_restudy_does_not_lock_delay_units():
    q = conversation_questions()[0]
    packet = retrieve_for_query(
        {
            "question": q,
            "card": _card("P::B::E291"),
            "requirements": {"max_units": 12},
            "split": "val",
        }
    )
    ids = _ids(packet)
    assert UID["restudy"] in ids
    assert UID["cod_delay"] not in ids
    assert UID["cod"] not in ids


def test_15_gip_followup_reuses_when_restudy_and_73_held():
    sess = _session_holding(
        [UID["restudy"], UID["cod_delay"]],
        "restudy notice and IC delay after GIA",
    )
    plan = heuristic_plan(conversation_questions()[4], sess)
    assert plan["need_search"] is False
    assert UID["restudy"] in (plan.get("reuse_unit_ids") or [])
    assert UID["cod_delay"] in (plan.get("reuse_unit_ids") or [])
