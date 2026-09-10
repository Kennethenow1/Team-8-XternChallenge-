"""Risk playbooks: BPM-015 index where a clause exists; stub otherwise.

Actions stay generic. Platinum 4 retrieved units outrank these bullets.
"""

from __future__ import annotations

from typing import Any

PLAYBOOKS: dict[str, dict[str, Any]] = {
    "abandonment": {
        "id": "pb_abandonment",
        "title": "Elevated withdrawal risk",
        "source": "bpm015_index",
        "actions": [
            "Treat P(quit) as a ranking input, not a guaranteed outcome.",
            "Check milestone security, offtake, and financing against the 12-month window.",
            "If the sponsor is serial-high, require extra diligence before restudy spend.",
        ],
    },
    "system_congestion": {
        "id": "pb_system_congestion",
        "title": "System delayed-MW crowding",
        "source": "bpm015_index",
        "actions": [
            "Use the pile as regime context (everyone late), not this plant’s COD.",
            "Stress study / construction calendars against a larger delayed stock 3 and 12 months out.",
            "Do not convert pile RMSE into a project-level month slip.",
        ],
    },
    "gia_execution": {
        "id": "pb_gia_execution",
        "title": "GIA / IA execution",
        "source": "bpm015_index",
        "actions": [
            "Switch the playbook from queue-entry screening to GIA milestone tracking.",
            "Confirm offtake, site control, and construction start vs the current ISD.",
        ],
    },
    "cod_already_slipped": {
        "id": "pb_cod_already_slipped",
        "title": "Service date already passed",
        "source": "bpm015_index",
        "actions": [
            "The date has already moved (fact). Do not ask the model for additional months of slip.",
            "Re-baseline offtake and interconnection milestones against the last known ISD.",
        ],
    },
    "developer_serial_quit": {
        "id": "pb_developer_serial",
        "title": "Sponsor withdrawal history",
        "source": "stub_until_policy_rag",
        "actions": [
            "Weight sponsor track record in credit / collateral discussions.",
            "Compare this project’s P(quit) to the sponsor’s prior withdrawal rate; do not double-count blindly.",
        ],
    },
    "restudy_friction": {
        "id": "pb_restudy",
        "title": "Restudy already on the record",
        "source": "bpm015_index",
        "actions": [
            "Flag restudy cost and delay as already-realized process risk.",
            "Scenario overlay `restudy` shows how P(quit) moves if another restudy is recorded — sensitivity, not physics.",
        ],
    },
    "hazard_exposure": {
        "id": "pb_hazard",
        "title": "Local FEMA hazard",
        "source": "stub_until_policy_rag",
        "actions": [
            "Bring county hazard into siting / insurance review; it is context, not a COD model.",
        ],
    },
    "cost_pressure": {
        "id": "pb_cost",
        "title": "Upgrade / network cost pressure",
        "source": "bpm015_index",
        "actions": [
            "Review assigned network upgrade cost vs MW before committing to the next study cycle.",
        ],
    },
    "policy_incentive": {
        "id": "pb_policy_incentive",
        "title": "Energy-community / IRA context",
        "source": "stub_until_policy_rag",
        "actions": [
            "IRA bonus-credit eligibility is a financing overlay. Replace this stub with the company policy PDF.",
        ],
    },
}


def playbook_ids_for(risk_codes: list[str]) -> list[str]:
    out: list[str] = []
    for code in risk_codes:
        pb = PLAYBOOKS.get(code)
        if pb:
            out.append(str(pb["id"]))
    return list(dict.fromkeys(out))
