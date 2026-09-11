"""CatBoost + Platinum 2 + Platinum 3 brief for Platinum 4.

Gold quit scores are CatBoost (`catboost_tuned` / trial-149). Not Electrum.
Not Platinum 1 delay-months CatBoost. 2024 stays sealed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.common.paths import REPO_ROOT
from src.modeling.platinum3.schema import DO_NOT_CLAIM, RISK_CODES
from src.modeling.platinum4.errors import TEST_SEALED, BotError
from src.modeling.platinum4.policy_index import STUB_RISKS

STACK_SCHEMA = "gold_stack.v1"
FULL_STACK_SCHEMA = "full_stack.v1"
SAMPLE_KEYS = ("P::B::E291", "P::J2280", "P::J2460")
DEFAULT_DATASET = REPO_ROOT / "platinum3" / "results" / "sample_cards.json"
DEFAULT_FIXTURE = REPO_ROOT / "platinum4" / "results" / "fixtures" / "full_stack_input.json"

# Display names the writer is allowed to use. Electrum is not one of them.
CATBOOST_LABEL = "CatBoost (gold freeze catboost_tuned / trial-149)"

HOW_TO_USE = [
    "CatBoost P(quit 12m) is a ranking score, not a BPM trigger and not a withdrawal verdict.",
    "Platinum 2 delayed MW is system crowding (EIA planned pile + Holt). It is not this plant's COD.",
    "The GIA-matched delayed-MW slice is a thin overlay. Do not treat it as the full GIA pile.",
    "Platinum 3 scenario delta is a sensitivity (if this state were on the row), not a causal law.",
    "Flags are current as-of facts. They do not create BPM duties by themselves.",
    "Only retrieved BPM-015 r33 units may be cited as procedure. Stubs stay under Gaps.",
    "Do not quote months of future COD slip. Platinum 1 delay-months CatBoost is not an input.",
]


def _round(x: Any, nd: int = 3) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return round(v, nd)


def _mw(x: Any) -> float | None:
    v = _round(x, 1)
    return v


def load_sample_cards(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or DEFAULT_DATASET
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run python scripts/run_platinum3_risk_cards.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a card list")
    return data


def select_card(
    cards: list[dict[str, Any]],
    project_key: str,
    scenario: str = "baseline",
) -> dict[str, Any]:
    key = (project_key or "").strip()
    scen = (scenario or "baseline").strip()
    for c in cards:
        if c.get("project_key") == key and (c.get("scenario") or {}).get("name") == scen:
            return c
    for c in cards:
        if c.get("project_key") == key:
            return c
    raise KeyError(f"no sample card for {project_key} scenario={scen}")


def catboost_quit(card: dict[str, Any]) -> dict[str, Any]:
    """Quit block. Always CatBoost. Never Electrum. Never Platinum 1 months."""
    raw_src = str(card.get("p_quit_source") or "catboost_tuned")
    freeze = raw_src == "catboost_tuned"
    return {
        "model": "catboost",
        "artifact": "catboost_tuned",
        "p_quit_12m": _round(card.get("p_quit_12m"), 3),
        "p_quit_12m_raw": _round(card.get("p_quit_12m_raw"), 3),
        "p_quit_under_scenario": _round(card.get("p_quit_under_scenario"), 3),
        "delta_p_quit": _round(card.get("delta_p_quit"), 4),
        "freeze_on_disk": freeze,
        "label": CATBOOST_LABEL,
        "honest_use": (
            "12-month quit probability from the gold CatBoost freeze (trial-149). "
            "Use for ranking. Do not treat as a BPM duty or a months-of-slip forecast."
        ),
    }


def platinum2_pile(card: dict[str, Any]) -> dict[str, Any]:
    pile = card.get("pile") or {}
    return {
        "engine": pile.get("pile_forecast_engine") or "holt_damped",
        "delayed_mw_now": _mw(pile.get("delayed_mw_now")),
        "delayed_mw_h3": _mw(pile.get("delayed_mw_h3")),
        "delayed_mw_h12": _mw(pile.get("delayed_mw_h12")),
        "gia_delayed_mw_now": _mw(pile.get("gia_delayed_mw_now")),
        "pile_percentile_pit": _round(pile.get("pile_percentile_pit"), 3),
        "pile_asof": pile.get("pile_asof"),
        "n_history": pile.get("n_history"),
        "honest_use": (
            "EIA planned delayed MW (delay ≥12m vs first seen). "
            "3m/12m are Holt from history ≤ as-of, not 2024 actuals. "
            "System stock, not this IR's commercial operation date."
        ),
    }


def risk_code_list(items: list[Any] | None) -> list[str]:
    out: list[str] = []
    for r in items or []:
        if isinstance(r, dict):
            c = r.get("code")
        else:
            c = r
        if c:
            out.append(str(c))
    return out


def classify_risks(card: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    bpm: list[dict[str, Any]] = []
    stubs: list[dict[str, Any]] = []
    for r in card.get("risks") or []:
        code = str(r.get("code") or "")
        row = {
            "code": code,
            "severity": r.get("severity"),
            "evidence": r.get("evidence"),
            "meaning": r.get("meaning") or RISK_CODES.get(code),
        }
        if code in STUB_RISKS:
            stubs.append(row)
        else:
            bpm.append(row)
    return {"bpm_index": bpm, "stubs": stubs}


def gold_stack_from_card(card: dict[str, Any] | None) -> dict[str, Any] | None:
    if not card:
        return None
    if not card.get("project_key") and card.get("p_quit_12m") is None:
        return None
    flags = dict(card.get("flags") or {})
    split = classify_risks(card)
    scen = card.get("scenario") or {}
    return {
        "schema_version": STACK_SCHEMA,
        "project": {
            "project_key": card.get("project_key"),
            "observation_date": card.get("observation_date"),
            "capacity_mw": card.get("capacity_mw"),
            "study_phase": card.get("study_phase"),
            "technology_primary": card.get("technology_primary"),
            "state_code": card.get("state_code"),
            "poi_name": card.get("poi_name"),
        },
        "catboost": catboost_quit(card),
        "platinum2": platinum2_pile(card),
        "platinum3": {
            "scenario": scen.get("name") or "baseline",
            "scenario_note": scen.get("note"),
            "flags": flags,
            "risks_bpm": split["bpm_index"],
            "risks_stub": split["stubs"],
            "playbook_ids": list(card.get("playbook_ids") or []),
        },
        "how_to_use": list(HOW_TO_USE),
        "do_not_claim": list(card.get("do_not_claim") or DO_NOT_CLAIM),
    }


def gold_stack_for_model(stack: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compact brief for gpt-4.1. No Electrum. No Platinum 1 months."""
    if not stack:
        return None
    cb = stack.get("catboost") or {}
    p2 = stack.get("platinum2") or {}
    p3 = stack.get("platinum3") or {}
    return {
        "project": stack.get("project"),
        "catboost": {
            "label": cb.get("label") or CATBOOST_LABEL,
            "p_quit_12m": cb.get("p_quit_12m"),
            "p_quit_under_scenario": cb.get("p_quit_under_scenario"),
            "delta_p_quit": cb.get("delta_p_quit"),
            "honest_use": cb.get("honest_use"),
        },
        "platinum2": {
            "delayed_mw_now": p2.get("delayed_mw_now"),
            "delayed_mw_h3": p2.get("delayed_mw_h3"),
            "delayed_mw_h12": p2.get("delayed_mw_h12"),
            "gia_delayed_mw_now": p2.get("gia_delayed_mw_now"),
            "pile_percentile_pit": p2.get("pile_percentile_pit"),
            "engine": p2.get("engine"),
            "honest_use": p2.get("honest_use"),
        },
        "platinum3": {
            "scenario": p3.get("scenario"),
            "scenario_note": p3.get("scenario_note"),
            "flags": p3.get("flags"),
            "risks_bpm": [
                {"code": r.get("code"), "severity": r.get("severity")}
                for r in (p3.get("risks_bpm") or [])
            ],
            "risks_stub": [r.get("code") for r in (p3.get("risks_stub") or [])],
        },
        "how_to_use": stack.get("how_to_use"),
    }


def attach_gold_stack(query: dict[str, Any], packet: dict[str, Any] | None = None) -> dict[str, Any] | None:
    card = (query or {}).get("card")
    stack = (query or {}).get("gold_stack") or gold_stack_from_card(card)
    if stack:
        query["gold_stack"] = stack
        if packet is not None:
            packet["gold_stack"] = stack
    return stack


def load_full_stack_input(
    raw: dict[str, Any] | Path | None = None,
    *,
    cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve a full_stack.v1 JSON (file or dict) into card + gold_stack + conversation."""
    if raw is None:
        raw = DEFAULT_FIXTURE
    if isinstance(raw, Path):
        payload = json.loads(raw.read_text(encoding="utf-8"))
    else:
        payload = dict(raw or {})
    split = str(payload.get("split") or "val")
    if split == "test":
        raise BotError(TEST_SEALED, "2024 test is sealed. Do not load full-stack split=test.")
    project_key = str(payload.get("project_key") or SAMPLE_KEYS[0])
    if project_key not in SAMPLE_KEYS:
        raise ValueError(f"only sample projects {SAMPLE_KEYS} are allowed")
    scenario = str(payload.get("scenario") or "baseline")
    dataset = payload.get("dataset")
    ds_path = REPO_ROOT / dataset if dataset else DEFAULT_DATASET
    card = payload.get("card")
    if not card:
        card = select_card(cards if cards is not None else load_sample_cards(ds_path), project_key, scenario)
    stack = gold_stack_from_card(card)
    conversation = list(payload.get("conversation") or [])
    if not conversation:
        from src.modeling.platinum4.full_stack_cases import TURNS

        conversation = list(TURNS)
    req = dict(payload.get("requirements") or {})
    req.setdefault("audience", "analyst")
    req.setdefault("dialect", "auto")
    req.setdefault("need", ["workflow", "stakeholders", "citations", "do_not_claim"])
    req.setdefault("max_units", 12)
    return {
        "schema_version": FULL_STACK_SCHEMA,
        "split": split,
        "project_key": project_key,
        "scenario": scenario,
        "card": card,
        "gold_stack": stack,
        "conversation": conversation,
        "requirements": req,
        "dataset": str(ds_path),
    }


def queries_from_full_stack(resolved: dict[str, Any]) -> list[dict[str, Any]]:
    req = dict(resolved.get("requirements") or {})
    out: list[dict[str, Any]] = []
    for turn in resolved.get("conversation") or []:
        need = list(turn.get("need") or req.get("need") or [])
        turn_req = {**req, "need": need}
        out.append(
            {
                "question": str(turn.get("question") or "").strip(),
                "card": resolved.get("card"),
                "gold_stack": resolved.get("gold_stack"),
                "requirements": turn_req,
                "split": resolved.get("split") or "val",
            }
        )
    return out
