"""UI helpers and mermaid keep/strip. No GPT required."""

from __future__ import annotations

import pytest

from src.modeling.platinum4.compose import (
    conceptual_mermaid,
    diagram_allowed,
    extract_mermaid,
    heuristic_plan,
    post_check,
)
from src.modeling.platinum4.session import empty_session
from src.modeling.platinum4.ui_api import (
    bootstrap,
    chat_about_study,
    reformat_study,
    stack_payload,
    study_question,
)


PACKET = {
    "retrieved": [
        {
            "unit_id": "bpm015-r33::5.4.6",
            "cite": "BPM-015 r33 §5.4.6",
            "title": "Interconnection Study Restudy",
            "pages": [56, 56],
        }
    ],
    "gaps": ["developer_serial_quit has no BPM-015 clause"],
    "do_not_claim": ["do not quote months of future COD slip as a model output"],
}

MAP = """```mermaid
flowchart TD
  misoNotice["MISO issues restudy notice"]
  icDecision["IC answers in 5 Business Days"]
  misoNotice --> icDecision
```

The Interconnection Customer answers after MISO notices.
"""


def test_bootstrap_is_catboost_not_electrum():
    meta = bootstrap()
    assert meta["model"] == "gpt-4.1"
    assert "CatBoost" in meta["quit_model"]
    assert "electrum" not in meta["quit_model"].lower()
    assert {p["project_key"] for p in meta["projects"]} == {"P::B::E291", "P::J2280", "P::J2460"}
    restudy = next(s for s in meta["scenarios"] if s["name"] == "restudy")
    assert restudy["label"] == "Extra restudy"
    assert restudy["summary"]
    assert restudy["expect"]
    assert all("label" in p and "summary" in p for p in meta["projects"])
    names = {f["name"] for f in meta["formats"]}
    assert names == {"long", "standard", "diagram", "citation_brief"}
    assert all("label" in f and "expect" in f for f in meta["formats"])
    assert "what_if" in meta["guides"]
    assert "format" in meta["guides"]


def test_stack_payload_catboost():
    view = stack_payload("P::B::E291", "restudy")
    assert view["gold_stack"]["catboost"]["model"] == "catboost"
    assert "electrum" not in str(view["brief"]).lower()
    assert view["gold_stack"]["platinum2"]["delayed_mw_now"] is not None


def test_diagram_allowed_shapes():
    assert diagram_allowed("long", False) is True
    assert diagram_allowed("standard", False) is True
    assert diagram_allowed("short", True) is False
    assert diagram_allowed("citation_brief", True) is False
    assert diagram_allowed("diagram", False) is True


def test_post_check_keeps_mermaid_on_long():
    md = (
        "# Interconnection procedure note\n\n"
        "## Situation\nThe inquiry concerns restudy after a peer withdrawal. This is not a legal opinion.\n\n"
        "## Workflow\nMISO shall notice a restudy. The IC shall answer within five Business Days (BPM-015 r33 §5.4.6).\n\n"
        f"## Procedure map\n{MAP}\n"
        "## Citations\n- BPM-015 r33 §5.4.6 - Restudy\n"
    )
    out, flags, invented = post_check(md, PACKET, shape="long", wants_diagram=True)
    assert not invented
    body = extract_mermaid(out)
    assert body and "flowchart" in body
    assert "MERMAID_INVALID" not in flags


def test_post_check_strips_mermaid_on_short():
    md = "The IC funds the restudy from remaining deposit (BPM-015 r33 §5.4.6).\n\n" + MAP
    out, flags, _ = post_check(md, PACKET, dialect="short", shape="short", wants_diagram=True)
    assert extract_mermaid(out) is None
    assert "flowchart TD" not in out


def test_fallback_mermaid_on_long_without_map():
    md = (
        "# Interconnection procedure note\n\n"
        "## Situation\nThe inquiry concerns restudy after a peer withdrawal. This is not a legal opinion.\n\n"
        "## Workflow\nMISO shall notice a restudy. The IC shall answer within five Business Days (BPM-015 r33 §5.4.6).\n"
    )
    out, flags, invented = post_check(md, PACKET, shape="long", wants_diagram=True)
    assert not invented
    body = extract_mermaid(out)
    assert body and "§5.4.6" in body
    assert "simple sequence" in out


def test_conceptual_mermaid_is_strict():
    src = conceptual_mermaid(PACKET, markdown="(BPM-015 r33 §5.4.6)")
    assert "flowchart TD" in src
    assert "style" not in src
    assert "click" not in src
    assert "§5.4.6" in src


def test_bootstrap_dataset_state():
    meta = bootstrap()
    ds = meta["dataset"]
    assert ds["split"] == "val"
    assert ds["n_projects"] == 3
    assert "2024" in ds["sealed"]
    assert "CatBoost" in meta["quit_model"]
    assert "electrum" not in meta["quit_model"].lower()


def test_study_question_names_overlay_not_electrum():
    q = study_question("restudy", "peer withdrawal funding")
    assert "`restudy`" not in q
    assert "one extra restudy" in q
    assert "CatBoost" in q
    assert "Electrum" not in q
    assert "peer withdrawal" in q


def test_chat_requires_pinned_study():
    with pytest.raises(ValueError, match="Generate a study first"):
        chat_about_study({}, session_id=None, question="Who pays for that?")


def test_reformat_requires_pinned_study():
    with pytest.raises(ValueError, match="Generate a study first"):
        reformat_study({}, session_id=None, fmt="standard")
