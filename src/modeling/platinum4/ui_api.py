"""HTTP helpers for the Platinum 4 briefing UI.

Generate a study once, then chat about that document. 2024 stays sealed.
Quit scores are CatBoost.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.modeling.platinum3.scenarios import SCENARIOS
from src.modeling.platinum4.compose import PINNED_MODEL, compose, extract_mermaid
from src.modeling.platinum4.errors import BotError
from src.modeling.platinum4.gold_stack import (
    CATBOOST_LABEL,
    DEFAULT_DATASET,
    SAMPLE_KEYS,
    gold_stack_from_card,
    gold_stack_for_model,
    load_sample_cards,
    select_card,
)
from src.modeling.platinum4.pipeline import run_turn
from src.modeling.platinum4.session import empty_session, history_for_model

NEED = ["workflow", "stakeholders", "citations", "do_not_claim"]
FORMATS = ("long", "standard", "diagram", "citation_brief")

# Plain-English chrome for the UI. Do not rewrite Platinum 3 SCENARIOS notes.
SCENARIO_COPY: dict[str, dict[str, str]] = {
    "baseline": {
        "label": "As it stands",
        "summary": "Numbers as observed. No extra what-if.",
        "expect": "A briefing of the project as recorded.",
        "prompt": "as it stands today, with no extra what-if",
    },
    "restudy": {
        "label": "Extra restudy",
        "summary": "Pretend one more restudy is already on the record.",
        "expect": "Restudy notice, funding, and Interconnection Customer clock language.",
        "prompt": "one extra restudy is already on the record",
    },
    "enter_gia": {
        "label": "GIA already signed",
        "summary": "Pretend the project has an executed GIA.",
        "expect": "Post-GIA delay or GIA procedure tracks if the clauses apply.",
        "prompt": "the project already has an executed GIA",
    },
    "already_past_cod": {
        "label": "Service date already missed",
        "summary": "Pretend the planned in-service date is more than a year past.",
        "expect": "Delay procedure, not a COD-month forecast.",
        "prompt": "the planned in-service date is already more than a year past",
    },
    "rate_shock": {
        "label": "Higher interest rates",
        "summary": "Pretend rates are two points higher than on the card.",
        "expect": "The same BPM duties. Quit chance is ranking context only.",
        "prompt": "interest rates are two points higher than on the card",
    },
    "serial_developer": {
        "label": "Sponsor often withdraws",
        "summary": "Pretend this sponsor's prior withdrawal rate is high.",
        "expect": "Gaps if there is no BPM clause for that risk.",
        "prompt": "this sponsor's prior withdrawal rate is already high",
    },
    "high_system_delay": {
        "label": "Queue is crowded",
        "summary": "Nearby delayed megawatts are treated as high. Quit chance may not move.",
        "expect": "Crowding as context, not a BPM trigger.",
        "prompt": "nearby delayed megawatts are treated as high",
    },
}

FORMAT_COPY: dict[str, dict[str, Any]] = {
    "long": {
        "name": "long",
        "label": "Full briefing",
        "summary": "Situation, who acts, clocks, citations, and limits.",
        "expect": "A complete procedure note with headings. Best first read.",
        "allows_map": True,
    },
    "standard": {
        "name": "standard",
        "label": "Short briefing",
        "summary": "Same clauses, fewer sections.",
        "expect": "A faster skim of the same procedure.",
        "allows_map": True,
    },
    "diagram": {
        "name": "diagram",
        "label": "Map first",
        "summary": "Flowchart first, then a short note.",
        "expect": "A procedure map, then brief supporting text.",
        "allows_map": True,
    },
    "citation_brief": {
        "name": "citation_brief",
        "label": "Citations only",
        "summary": "Clause list, almost no prose.",
        "expect": "Cites only. Use when you only need the references.",
        "allows_map": False,
    },
}

PHASE_COPY = {
    "IA Executed": "GIA already signed",
    "System Impact Study": "in a system impact study",
    "Not Started": "study not started",
}

EXAMPLES = [
    {
        "id": "restudy",
        "label": "Peer withdrawal restudy",
        "focus": "A peer project withdraws: who notices, who funds the restudy, and how long the Interconnection Customer has to answer.",
        "project_key": "P::B::E291",
        "scenario": "restudy",
        "kind": "study",
    },
    {
        "id": "dp2",
        "label": "Decision Point II",
        "focus": "What happens at Decision Point II, including M3/M4 and D2.",
        "project_key": "P::J2280",
        "scenario": "baseline",
        "kind": "study",
    },
    {
        "id": "clock",
        "label": "Who pays, and how many days?",
        "question": "Who pays for that, and how many Business Days does the Interconnection Customer have?",
        "kind": "chat",
    },
    {
        "id": "map",
        "label": "Walk the map",
        "question": "Walk the procedure map in the briefing. Who acts first?",
        "kind": "chat",
    },
]


def dataset_state(cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cards = cards if cards is not None else load_sample_cards()
    dates = sorted({str(c.get("observation_date")) for c in cards if c.get("observation_date")})
    scenarios = []
    for c in cards:
        name = (c.get("scenario") or {}).get("name")
        if name and name not in scenarios:
            scenarios.append(name)
    keys = [k for k in SAMPLE_KEYS if any(c.get("project_key") == k for c in cards)]
    return {
        "path": "platinum3/results/sample_cards.json",
        "dataset": str(DEFAULT_DATASET.name),
        "split": "val",
        "year": "2023",
        "sealed": "2024 test is sealed. These cards are 2023 val samples only.",
        "n_cards": len(cards),
        "n_projects": len(keys),
        "projects": keys,
        "scenarios": scenarios,
        "observation_dates": dates,
        "as_of": dates[-1] if dates else None,
        "quit_model": CATBOOST_LABEL,
        "pile": "Platinum 2 Holt on EIA delayed planned MW",
        "policy": "BPM-015 r33 clean",
        "composer": PINNED_MODEL,
    }


def _projects() -> list[dict[str, Any]]:
    cards = load_sample_cards()
    seen: dict[str, dict[str, Any]] = {}
    for c in cards:
        key = c.get("project_key")
        if key not in SAMPLE_KEYS or key in seen:
            continue
        if (c.get("scenario") or {}).get("name") != "baseline":
            continue
        letter = {k: chr(ord("A") + i) for i, k in enumerate(SAMPLE_KEYS)}.get(key, "?")
        phase = str(c.get("study_phase") or "")
        phase_en = PHASE_COPY.get(phase, phase or "phase unknown")
        tech = str(c.get("technology_primary") or "project")
        state_code = c.get("state_code") or ""
        mw = c.get("capacity_mw")
        mw_txt = f"{mw:g} MW" if isinstance(mw, (int, float)) else "capacity unknown"
        loc = f"{state_code} " if state_code else ""
        seen[key] = {
            "project_key": key,
            "letter": letter,
            "label": f"Sample {letter}: {loc}{tech}, {mw_txt}",
            "summary": f"{phase_en}. Point of interconnection: {c.get('poi_name') or 'not listed'}.",
            "study_phase": c.get("study_phase"),
            "capacity_mw": c.get("capacity_mw"),
            "technology_primary": c.get("technology_primary"),
            "state_code": c.get("state_code"),
            "poi_name": c.get("poi_name"),
            "observation_date": c.get("observation_date"),
        }
    return [seen[k] for k in SAMPLE_KEYS if k in seen]


def _scenarios() -> list[dict[str, str]]:
    rows = []
    for name, spec in SCENARIOS.items():
        copy = SCENARIO_COPY.get(name) or {}
        rows.append(
            {
                "name": name,
                "label": copy.get("label") or name.replace("_", " "),
                "summary": copy.get("summary") or "",
                "expect": copy.get("expect") or "",
                "detail": spec.get("note") or "",
                "note": spec.get("note") or "",
            }
        )
    return rows


def _formats() -> list[dict[str, Any]]:
    return [dict(FORMAT_COPY[name]) for name in FORMATS if name in FORMAT_COPY]


def bootstrap() -> dict[str, Any]:
    return {
        "model": PINNED_MODEL,
        "quit_model": CATBOOST_LABEL,
        "sealed": "2024 test is sealed. Sample cards are 2023 val only.",
        "dataset": dataset_state(),
        "projects": _projects(),
        "scenarios": _scenarios(),
        "formats": _formats(),
        "examples": EXAMPLES,
        "need": list(NEED),
        "guides": {
            "what_if": (
                "A what-if changes the numbers on this sample card so you can ask "
                "what the procedure would look like if something were already true. "
                "It is not a new MISO restudy, and it is not a prediction that the event will happen."
            ),
            "format": (
                "The briefing shape only changes how the same BPM text is written. "
                "It does not search again. After a briefing exists, Change layout rewrites "
                "the same document in another shape."
            ),
            "project": (
                "These are three 2023 sample interconnection requests, not the full queue. "
                "2024 test labels stay sealed."
            ),
        },
    }


def stack_payload(project_key: str, scenario: str) -> dict[str, Any]:
    key = (project_key or "").strip()
    if key not in SAMPLE_KEYS:
        raise ValueError(f"only sample projects {SAMPLE_KEYS} are allowed")
    card = select_card(load_sample_cards(), key, scenario or "baseline")
    stack = gold_stack_from_card(card)
    return {
        "project_key": key,
        "scenario": (card.get("scenario") or {}).get("name"),
        "dataset": dataset_state(),
        "gold_stack": stack,
        "brief": gold_stack_for_model(stack),
    }


def study_question(scenario: str, focus: str = "") -> str:
    scen = (scenario or "baseline").strip()
    copy = SCENARIO_COPY.get(scen) or {}
    what_if = copy.get("prompt") or copy.get("label") or scen.replace("_", " ")
    core = (
        f"Write one BPM-015 r33 procedure study for this interconnection request. "
        f"What-if: {what_if}. "
        "Read CatBoost P(quit) and Platinum 2 delayed MW as context only, not as BPM duties. "
        "Stub risks stay under Gaps. Walk the procedures this card actually implicates."
    )
    extra = (focus or "").strip()
    if extra:
        return core + " Focus the study on: " + extra
    return core


def slim_units(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for u in packet.get("retrieved") or []:
        rows.append(
            {
                "unit_id": u.get("unit_id"),
                "cite": u.get("cite"),
                "title": u.get("title"),
                "pages": u.get("pages"),
            }
        )
    return rows


def _study_from_result(result: dict[str, Any], *, question: str, project_key: str, scenario: str, fmt: str) -> dict[str, Any]:
    composed = result.get("composed") or {}
    packet = result.get("packet") or {}
    plan = result.get("plan") or {}
    md = composed.get("markdown") or ""
    stack = packet.get("gold_stack")
    return {
        "question": question,
        "project_key": project_key,
        "scenario": scenario,
        "format": fmt,
        "markdown": md,
        "mermaid": extract_mermaid(md),
        "shape": composed.get("shape") or plan.get("response_shape"),
        "searched": result.get("searched"),
        "plan_reason": plan.get("reason"),
        "model": composed.get("model") or PINNED_MODEL,
        "compliance": (packet.get("compliance") or {}).get("status") or "not_determined",
        "units": slim_units(packet),
        "gaps": list(packet.get("gaps") or []),
        "do_not_claim": list(packet.get("do_not_claim") or []),
        "gold_stack": gold_stack_for_model(stack) if isinstance(stack, dict) else None,
        "packet": packet,
        "error_code": composed.get("error_code") or packet.get("error_code"),
    }


def session_view(state: dict[str, Any], *, reply: dict[str, Any] | None = None) -> dict[str, Any]:
    study = state.get("study") or {}
    public_study = {k: v for k, v in study.items() if k != "packet"} if study else None
    return {
        "session_id": state["id"],
        "project_key": state.get("project_key"),
        "scenario": state.get("scenario"),
        "format": state.get("format"),
        "has_study": bool(study),
        "study": public_study,
        "messages": state.get("messages") or [],
        "reply": reply,
        "error": False,
    }


def new_ui_session(project_key: str, scenario: str, fmt: str = "long") -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "project_key": project_key,
        "scenario": scenario,
        "format": fmt,
        "bot": empty_session(),
        "study": None,
        "messages": [],
    }


def _run_query(state: dict[str, Any], query: dict[str, Any]) -> dict[str, Any]:
    return run_turn(query, state["bot"])


def generate_study(
    sessions: dict[str, dict[str, Any]],
    *,
    session_id: str | None,
    project_key: str,
    scenario: str,
    focus: str = "",
    fmt: str = "long",
    want_diagram: bool = True,
) -> dict[str, Any]:
    key = (project_key or "").strip()
    if key not in SAMPLE_KEYS:
        raise ValueError(f"only sample projects {SAMPLE_KEYS} are allowed")
    scen = (scenario or "baseline").strip()
    fmt = fmt if fmt in FORMATS else "long"
    state = new_ui_session(key, scen, fmt)
    if session_id and sessions.get(session_id):
        prev = sessions[session_id]
        if prev.get("project_key") == key and prev.get("scenario") == scen:
            state["id"] = session_id
    card = select_card(load_sample_cards(), key, scen)
    question = study_question(scen, focus)
    dialect = "diagram" if fmt == "diagram" else fmt
    query = {
        "question": question,
        "card": card,
        "mode": "study",
        "want_diagram": bool(want_diagram) or fmt == "diagram",
        "requirements": {
            "audience": "analyst",
            "dialect": dialect,
            "need": list(NEED),
            "max_units": 12,
        },
        "split": "val",
    }
    try:
        result = _run_query(state, query)
    except BotError as exc:
        sessions[state["id"]] = state
        return {
            "error": True,
            "error_code": exc.code,
            "message": str(exc),
            "session_id": state["id"],
            "has_study": False,
        }
    state["bot"] = result["session"]
    state["study"] = _study_from_result(result, question=question, project_key=key, scenario=scen, fmt=fmt)
    state["messages"] = [
        {
            "role": "system",
            "text": (
                f"Briefing pinned for {key}. Questions refer to this document. "
                "Changing layout restyles it; it does not start a new briefing."
            ),
        }
    ]
    sessions[state["id"]] = state
    return session_view(state)


def reformat_study(
    sessions: dict[str, dict[str, Any]],
    *,
    session_id: str | None,
    fmt: str,
    want_diagram: bool = True,
) -> dict[str, Any]:
    state = sessions.get(session_id or "")
    if not state or not state.get("study"):
        raise ValueError("Generate a study first, then change its format.")
    fmt = fmt if fmt in FORMATS else "long"
    packet = dict(state["study"].get("packet") or {})
    if not packet:
        raise ValueError("Pinned study has no packet to restyle.")
    packet["wants_diagram"] = bool(want_diagram) or fmt == "diagram"
    q = dict(packet.get("query") or {})
    q["mode"] = "reformat"
    q["want_diagram"] = packet["wants_diagram"]
    packet["query"] = q
    shape = "diagram" if fmt == "diagram" else fmt
    plan = {
        "mode": "reformat",
        "need_search": False,
        "want_diagram": bool(want_diagram) or fmt == "diagram",
        "response_shape": shape,
        "reason": "reformat pinned study; same retrieved units",
    }
    composed = compose(
        packet,
        dialect=fmt,
        shape=shape,
        history=history_for_model(state["bot"]),
        plan=plan,
    )
    md = composed.get("markdown") or ""
    state["format"] = fmt
    state["study"] = {
        **state["study"],
        "format": fmt,
        "markdown": md,
        "mermaid": extract_mermaid(md),
        "shape": composed.get("shape") or shape,
        "searched": False,
        "plan_reason": plan["reason"],
        "packet": packet,
        "units": slim_units(packet),
    }
    sessions[state["id"]] = state
    return session_view(state)


def chat_about_study(
    sessions: dict[str, dict[str, Any]],
    *,
    session_id: str | None,
    question: str,
) -> dict[str, Any]:
    qtext = (question or "").strip()
    if not qtext:
        raise ValueError("question is required")
    state = sessions.get(session_id or "")
    if not state or not (state.get("study") or {}).get("markdown"):
        raise ValueError("Generate a study first. Chat refers to that document; it does not write a new one.")
    study = state["study"]
    card = select_card(load_sample_cards(), state["project_key"], state["scenario"])
    query = {
        "question": qtext,
        "card": card,
        "mode": "chat",
        "want_diagram": False,
        "pinned_study": (study.get("markdown") or "")[:6000],
        "requirements": {
            "audience": "analyst",
            "dialect": "short",
            "need": ["citations", "do_not_claim"],
            "max_units": 12,
        },
        "split": "val",
    }
    try:
        result = _run_query(state, query)
    except BotError as exc:
        return {
            "error": True,
            "error_code": exc.code,
            "message": str(exc),
            "session_id": state["id"],
            "has_study": True,
            "study": {k: v for k, v in study.items() if k != "packet"},
            "messages": state.get("messages") or [],
        }
    state["bot"] = result["session"]
    composed = result.get("composed") or {}
    md = composed.get("markdown") or ""
    reply = {
        "markdown": md,
        "shape": composed.get("shape") or "short",
        "searched": result.get("searched"),
        "units": slim_units(result.get("packet") or {}),
        "model": composed.get("model") or PINNED_MODEL,
    }
    state["messages"].append({"role": "user", "text": qtext})
    state["messages"].append({"role": "assistant", "markdown": md, "shape": reply["shape"], "searched": reply["searched"]})
    sessions[state["id"]] = state
    return session_view(state, reply=reply)


def run_ui_turn(
    sessions: dict[str, dict[str, Any]],
    *,
    session_id: str | None,
    question: str,
    project_key: str,
    scenario: str,
    want_diagram: bool = True,
    reset: bool = False,
    mode: str = "chat",
    fmt: str = "long",
    focus: str = "",
) -> dict[str, Any]:
    """Dispatch UI actions. `study` writes the pinned document; `chat` does not."""
    mode = (mode or "chat").strip().lower()
    if mode in {"study", "generate"}:
        return generate_study(
            sessions,
            session_id=None if reset else session_id,
            project_key=project_key,
            scenario=scenario,
            focus=focus or question,
            fmt=fmt,
            want_diagram=want_diagram,
        )
    if mode == "reformat":
        return reformat_study(sessions, session_id=session_id, fmt=fmt, want_diagram=want_diagram)
    return chat_about_study(sessions, session_id=session_id, question=question)
