"""Gold stack: CatBoost + Platinum 2 + Platinum 3. No GPT required."""

from __future__ import annotations

import json

import pytest

from src.modeling.platinum4.errors import TEST_SEALED, BotError
from src.modeling.platinum4.gold_stack import (
    CATBOOST_LABEL,
    DEFAULT_FIXTURE,
    gold_stack_for_model,
    gold_stack_from_card,
    load_full_stack_input,
    load_sample_cards,
    queries_from_full_stack,
    risk_code_list,
    select_card,
)
from src.modeling.platinum4.search import retrieve_for_query


def test_fixture_loads_restudy_card_as_catboost_not_electrum():
    resolved = load_full_stack_input(DEFAULT_FIXTURE)
    assert resolved["project_key"] == "P::B::E291"
    assert resolved["scenario"] == "restudy"
    card = resolved["card"]
    assert (card.get("scenario") or {}).get("name") == "restudy"
    assert card.get("flags", {}).get("restudy_on_record") is True
    stack = resolved["gold_stack"]
    assert stack["catboost"]["model"] == "catboost"
    assert stack["catboost"]["label"] == CATBOOST_LABEL
    assert "electrum" not in json.dumps(stack).lower()
    brief = gold_stack_for_model(stack)
    assert "electrum" not in json.dumps(brief).lower()
    assert brief["catboost"]["p_quit_12m"] is not None
    p2 = stack["platinum2"]
    assert p2["delayed_mw_now"] and p2["delayed_mw_h12"]
    assert "developer_serial_quit" in {r["code"] for r in stack["platinum3"]["risks_stub"]}
    qs = queries_from_full_stack(resolved)
    assert len(qs) == 3
    assert all(q["gold_stack"]["catboost"]["model"] == "catboost" for q in qs)


def test_select_card_from_dataset():
    cards = load_sample_cards()
    base = select_card(cards, "P::B::E291", "baseline")
    restudy = select_card(cards, "P::B::E291", "restudy")
    assert (base.get("scenario") or {}).get("name") == "baseline"
    assert restudy["flags"]["restudy_on_record"] is True
    assert restudy["p_quit_under_scenario"] is not None


def test_gold_stack_from_card_splits_stubs():
    card = {
        "project_key": "P::B::E291",
        "p_quit_12m": 0.07,
        "p_quit_source": "electrum_catboost",
        "pile": {
            "delayed_mw_now": 100.0,
            "delayed_mw_h12": 120.0,
            "pile_forecast_engine": "holt_damped",
        },
        "flags": {"is_gia": True},
        "scenario": {"name": "baseline", "note": "Observed state; no overlay."},
        "risks": [
            {"code": "gia_execution", "severity": "medium"},
            {"code": "developer_serial_quit", "severity": "medium"},
            {"code": "hazard_exposure", "severity": "low"},
        ],
    }
    stack = gold_stack_from_card(card)
    assert stack["catboost"]["model"] == "catboost"
    assert "electrum" not in json.dumps(gold_stack_for_model(stack)).lower()
    assert risk_code_list(stack["platinum3"]["risks_stub"]) == [
        "developer_serial_quit",
        "hazard_exposure",
    ]


def test_full_stack_split_test_sealed():
    with pytest.raises(BotError) as exc:
        load_full_stack_input(
            {"split": "test", "project_key": "P::B::E291", "scenario": "baseline"}
        )
    assert exc.value.code == TEST_SEALED


def test_retrieve_packet_includes_gold_stack():
    resolved = load_full_stack_input(DEFAULT_FIXTURE)
    q = queries_from_full_stack(resolved)[1]
    packet = retrieve_for_query(q)
    stack = packet.get("gold_stack") or {}
    assert stack.get("catboost", {}).get("model") == "catboost"
    assert "electrum" not in json.dumps(stack).lower()
    ids = [u.get("unit_id") for u in (packet.get("retrieved") or [])]
    assert "bpm015-r33::5.4.6" in ids
