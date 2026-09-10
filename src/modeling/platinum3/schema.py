"""Risk-card contract. These codes are what GPT is allowed to talk about."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "platinum3.v1"

DO_NOT_CLAIM = [
    "do not quote months of future COD slip as a model output",
    "do not claim a MISO Step-Up / Firm Service failure record",
    "do not treat EIA delayed MW as a complete GIA list (overlay is thin)",
    "do not treat scenario deltas as causal effects",
    "do not use FERC-730 as a clean delay source",
    "do not unseal 2024 test labels or tune on test/score",
]

RISK_CODES = {
    "abandonment": "Project is at elevated chance of leaving the queue in ~12 months.",
    "system_congestion": "The planned delayed-MW pile is large versus history (system crowding).",
    "gia_execution": "Project is in GIA / IA — execution and offtake risk, not just study-queue risk.",
    "cod_already_slipped": "Planned service date is already at or before the as-of date.",
    "developer_serial_quit": "This sponsor’s prior projects withdrew at a high rate.",
    "restudy_friction": "Study restudies are already on the record.",
    "hazard_exposure": "County FEMA risk is high versus the training distribution.",
    "cost_pressure": "Network upgrade cost or cost-per-MW is elevated.",
    "policy_incentive": "Energy-community / IRA bonus-credit flag is on (financing context, not a delay model).",
}

# Decision thresholds for the bot (not HPO). p_quit_high matches freeze Strong PR-AUC spirit, not val leakage.
DEFAULT_THRESHOLDS = {
    "p_quit_high": 0.10,
    "p_quit_medium": 0.05,
    "developer_serial_quantile": 0.75,
    "fema_high_quantile": 0.75,
    "pile_crowded_percentile": 0.75,
    "upgrade_cost_quantile": 0.75,
}

SEVERITY_ORDER = {"high": 2, "medium": 1, "low": 0}


def empty_card_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_key": None,
        "observation_date": None,
        "capacity_mw": None,
        "study_phase": None,
        "technology_primary": None,
        "state_code": None,
        "p_quit_12m_raw": None,
        "p_quit_12m": None,
        "p_quit_source": None,
        "pile": {},
        "flags": {},
        "scenario": {"name": "baseline", "note": "Observed state; no overlay."},
        "p_quit_under_scenario": None,
        "delta_p_quit": 0.0,
        "risks": [],
        "playbook_ids": [],
        "do_not_claim": list(DO_NOT_CLAIM),
    }
