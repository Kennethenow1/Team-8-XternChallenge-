"""Platinum 4: Platinum 3 risk card -> BPM-015 procedure units.

No embeddings. No ChatGPT. Cap 8–12 units. Compliance is never scored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.modeling.platinum3.playbooks import PLAYBOOKS
from src.modeling.platinum4.policy_index import (
    INDEX_DIR,
    MAP_DIR,
    STUB_RISKS,
)
from src.modeling.platinum3.schema import DO_NOT_CLAIM
from src.modeling.platinum4.gold_stack import gold_stack_from_card

BOT_SCHEMA = "bot.v1"
MAX_UNITS = 12

# GIQ study_phase is coarser than DPP 1/2/3.
STUDY_PHASE_TO_GI = {
    "not started": ["pre_queue"],
    "feasibility study": ["application_review"],
    "in progress (unknown study)": ["application_review"],
    "system impact study": ["dpp1", "dpp2"],
    "facility study": ["dpp3"],
    "ia executed": ["gia", "post_gia"],
    "ia pending": ["gia", "post_gia"],
    "gia": ["gia", "post_gia"],
    "operational": ["post_gia"],
}

FLAG_TOPICS = {
    "restudy_on_record": ["restudy"],
    "cod_already_slipped": ["delay_of_study", "commercial_operation"],
    "pile_crowded": ["cost_allocation"],
    "upgrade_cost_high": ["cost_allocation", "deposit_refund"],
    "is_gia": ["gia_negotiation"],
}


def load_units() -> list[dict[str, Any]]:
    path = INDEX_DIR / "units.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run python scripts/build_miso_policy_index.py")
    units = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            units.append(json.loads(line))
    return units


def load_risk_map() -> dict[str, Any]:
    path = MAP_DIR / "risk_code_to_units.json"
    return json.loads(path.read_text(encoding="utf-8"))


def gi_phases_for_card(card: dict[str, Any]) -> list[str]:
    phases: list[str] = []
    raw = str(card.get("study_phase") or "").strip().lower()
    phases.extend(STUDY_PHASE_TO_GI.get(raw, []))
    flags = card.get("flags") or {}
    if flags.get("is_gia"):
        for p in ("gia", "post_gia"):
            if p not in phases:
                phases.append(p)
    if not phases:
        phases = ["application_review"]
    return phases


def risk_codes_for_card(card: dict[str, Any]) -> list[str]:
    codes = [r.get("code") for r in (card.get("risks") or []) if r.get("code")]
    return list(dict.fromkeys(codes))


def _flag_topics(card: dict[str, Any]) -> list[str]:
    flags = card.get("flags") or {}
    topics = []
    for flag, tops in FLAG_TOPICS.items():
        if flags.get(flag):
            topics.extend(tops)
    return list(dict.fromkeys(topics))


def _section_family(num: str) -> str:
    parts = str(num).split(".")
    if str(num).startswith("app"):
        return str(num)
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return str(num)


def _score_unit(unit: dict[str, Any], phases: list[str], risks: list[str], topics: list[str]) -> float:
    tags = unit.get("tags") or {}
    score = 0.0
    if set(tags.get("gi_phase") or []) & set(phases):
        score += 2.0
    overlap_risks = set(tags.get("risk_code") or []) & set(risks)
    if overlap_risks:
        score += 3.0
    if set(tags.get("topic") or []) & set(topics):
        score += 1.0
    claim = tags.get("claim_class") or []
    if "workflow" in claim:
        score += 2.0
    if "study_method" in claim and "workflow" not in claim:
        score -= 2.0
    if "do_not_use_as_legal_opinion" in claim:
        score -= 4.0
    num = str((unit.get("source") or {}).get("bpm_section") or "")
    score += 0.2 * min(num.count("."), 4)
    if "cod_already_slipped" in risks and "cod_already_slipped" in (tags.get("risk_code") or []):
        score += 2.5
    if "restudy_friction" in risks and "restudy" in (tags.get("topic") or []):
        score += 2.0
    if "post_gia" in phases and "post_gia" in (tags.get("gi_phase") or []):
        score += 1.5
    return score


PACKET_TEXT_CAP = 4000


def _slim(unit: dict[str, Any]) -> dict[str, Any]:
    text = unit.get("text") or ""
    if len(text) > PACKET_TEXT_CAP:
        text = text[: PACKET_TEXT_CAP].rstrip() + "\n…"
    return {
        "unit_id": unit["unit_id"],
        "cite": unit.get("cite"),
        "title": (unit.get("source") or {}).get("title"),
        "bpm_section": (unit.get("source") or {}).get("bpm_section"),
        "pages": (unit.get("source") or {}).get("pages"),
        "tags": unit.get("tags"),
        "text": text,
    }


def assemble_bot_packet(
    card: dict[str, Any] | None,
    picked: list[dict[str, Any]],
    units: list[dict[str, Any]],
    phases: list[str],
    risks: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wanted: dict[str, dict[str, Any]] = {u["unit_id"]: u for u in units}
    risk_map = load_risk_map()
    card = card or {}
    actor_hits: dict[str, list[str]] = {}
    for u in picked:
        for sh in u.get("stakeholders") or []:
            actor = sh.get("actor")
            if not actor:
                continue
            actor_hits.setdefault(actor, []).append(u["unit_id"])
    stakeholders = [
        {"actor": actor, "why": "", "unit_ids": ids[:8]} for actor, ids in actor_hits.items()
    ]
    for sh in stakeholders:
        for u in picked:
            for row in u.get("stakeholders") or []:
                if row.get("actor") == sh["actor"]:
                    sh["why"] = row.get("impact")
                    break
    mitigation = []
    for code in risks:
        pb = PLAYBOOKS.get(code) or {}
        entry = risk_map.get(code) or {}
        cites = []
        for uid in (entry.get("unit_ids") or [])[:4]:
            u = wanted.get(uid)
            if u:
                cites.append(u.get("cite"))
        source = "bpm015_index" if (entry.get("unit_ids") and code not in STUB_RISKS) else "stub_until_policy_rag"
        if code in STUB_RISKS:
            source = "stub_until_policy_rag"
        mitigation.append(
            {
                "risk_code": code,
                "actions": list(pb.get("actions") or []),
                "citations": cites,
                "playbook_id": pb.get("id"),
                "source": source,
                "bpm_note": entry.get("note"),
            }
        )
    workflow_units = [
        u for u in picked if "workflow" in ((u.get("tags") or {}).get("claim_class") or [])
    ]
    next_steps = [f"{u.get('cite')}: {(u.get('source') or {}).get('title')}" for u in workflow_units[:6]]
    packet = {
        "schema_version": BOT_SCHEMA,
        "card": {
            "project_key": card.get("project_key"),
            "observation_date": card.get("observation_date"),
            "study_phase": card.get("study_phase"),
            "scenario": card.get("scenario"),
            "p_quit_12m": card.get("p_quit_12m"),
            "flags": card.get("flags"),
            "risks": card.get("risks"),
        },
        "workflow": {
            "gi_phase_guess": phases,
            "next_steps": next_steps,
            "note": "GIQ study_phase is coarser than DPP 1/2/3. Phase guess is best-effort.",
        },
        "stakeholders": stakeholders,
        "mitigation": mitigation,
        "compliance": {
            "status": "not_determined",
            "meaning": "We do not score legal compliance of a COD slip. Retrieved delay/restudy/withdrawal clauses only.",
        },
        "retrieved": [_slim(u) for u in picked],
        "do_not_claim": list(card.get("do_not_claim") or DO_NOT_CLAIM),
    }
    extra = dict(extra or {})
    stack = extra.pop("gold_stack", None) or gold_stack_from_card(card)
    if stack:
        packet["gold_stack"] = stack
    if extra:
        packet.update(extra)
    return packet


def retrieve_for_card(card: dict[str, Any], *, units: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    units = units if units is not None else load_units()
    risk_map = load_risk_map()
    phases = gi_phases_for_card(card)
    risks = risk_codes_for_card(card)
    topics = _flag_topics(card)

    seed_ids: list[str] = []
    for r in risks:
        entry = risk_map.get(r) or {}
        seed_ids.extend(entry.get("unit_ids") or [])

    scored = []
    for u in units:
        uid = u["unit_id"]
        claim = (u.get("tags") or {}).get("claim_class") or []
        if "do_not_use_as_legal_opinion" in claim and not (set((u.get("tags") or {}).get("risk_code") or []) & set(risks)):
            continue
        if "study_method" in claim and "workflow" not in claim and uid not in seed_ids:
            continue
        s = _score_unit(u, phases, risks, topics)
        if uid in seed_ids:
            s += 5.0
        if s > 0:
            scored.append((s, u))
    scored.sort(key=lambda x: -x[0])
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    family_n: dict[str, int] = {}
    for s, u in scored:
        uid = u["unit_id"]
        if uid in seen:
            continue
        num = str((u.get("source") or {}).get("bpm_section") or "")
        fam = _section_family(num)
        cap = 3 if uid in seed_ids else 2
        if family_n.get(fam, 0) >= cap:
            continue
        seen.add(uid)
        family_n[fam] = family_n.get(fam, 0) + 1
        picked.append(u)
        if len(picked) >= MAX_UNITS:
            break
    return assemble_bot_packet(card, picked, units, phases, risks)


SAMPLE_SCENARIOS = ("baseline", "restudy", "enter_gia", "already_past_cod")


def write_sample_packets(sample_cards: list[dict[str, Any]], dest: Path) -> Path:
    units = load_units()
    packets = []
    seen: set[tuple[Any, Any]] = set()
    for c in sample_cards:
        sc = (c.get("scenario") or {}).get("name")
        if sc not in SAMPLE_SCENARIOS:
            continue
        key = (c.get("project_key"), sc)
        if key in seen:
            continue
        seen.add(key)
        packets.append(retrieve_for_card(c, units=units))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(packets, indent=2, default=str), encoding="utf-8")
    return dest
