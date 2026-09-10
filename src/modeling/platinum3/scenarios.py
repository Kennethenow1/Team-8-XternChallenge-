"""Scenario overlays: mutate observed Electrum features and re-score.

These are sensitivities (if this state were on the row), not causal effects.
`high_system_delay` does not change CatBoost X; crowding lives on the pile slot.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from src.gold.cod_delay import GIA_PHASES

ApplyFn = Callable[[pd.DataFrame], pd.DataFrame]

GIA_OVERLAY_PHASE = "IA Executed"  # in GIA_PHASES and present on val
assert GIA_OVERLAY_PHASE in GIA_PHASES


def _copy(X: pd.DataFrame) -> pd.DataFrame:
    return X.copy()


def _enter_gia(X: pd.DataFrame) -> pd.DataFrame:
    out = _copy(X)
    if "study_phase" in out.columns:
        out["study_phase"] = GIA_OVERLAY_PHASE
    return out


def _already_past_cod(X: pd.DataFrame) -> pd.DataFrame:
    out = _copy(X)
    if "service_date_passed" in out.columns:
        out["service_date_passed"] = 1
    if "months_until_service" in out.columns:
        cur = pd.to_numeric(out["months_until_service"], errors="coerce")
        out["months_until_service"] = cur.where(cur.le(-12), -12.0)
    if "service_date_shift_months" in out.columns:
        cur = pd.to_numeric(out["service_date_shift_months"], errors="coerce").fillna(0.0)
        out["service_date_shift_months"] = cur.clip(lower=0) + 12.0
    return out


def _restudy(X: pd.DataFrame) -> pd.DataFrame:
    out = _copy(X)
    if "restudy_count" in out.columns:
        cur = pd.to_numeric(out["restudy_count"], errors="coerce").fillna(0.0)
        out["restudy_count"] = cur + 1.0
    return out


def _rate_shock(X: pd.DataFrame) -> pd.DataFrame:
    out = _copy(X)
    if "interest_rate_at_observation" in out.columns:
        cur = pd.to_numeric(out["interest_rate_at_observation"], errors="coerce")
        out["interest_rate_at_observation"] = cur + 2.0
    if "interest_rate_change_since_entry" in out.columns:
        cur = pd.to_numeric(out["interest_rate_change_since_entry"], errors="coerce").fillna(0.0)
        out["interest_rate_change_since_entry"] = cur + 2.0
    return out


def _serial_developer(X: pd.DataFrame) -> pd.DataFrame:
    out = _copy(X)
    if "developer_prior_withdrawal_rate" in out.columns:
        cur = pd.to_numeric(out["developer_prior_withdrawal_rate"], errors="coerce").fillna(0.0)
        out["developer_prior_withdrawal_rate"] = cur.clip(lower=0.75)
    return out


def _identity(X: pd.DataFrame) -> pd.DataFrame:
    return _copy(X)


SCENARIOS: dict[str, dict[str, Any]] = {
    "baseline": {
        "name": "baseline",
        "note": "Observed state; no overlay.",
        "changes_features": False,
        "apply": _identity,
    },
    "enter_gia": {
        "name": "enter_gia",
        "note": "If study_phase were IA Executed (GIA/IA). Sensitivity, not a causal GIA effect.",
        "changes_features": True,
        "apply": _enter_gia,
    },
    "already_past_cod": {
        "name": "already_past_cod",
        "note": "If the planned service date were already 12+ months past as-of. Fact overlay, not Platinum 1 months.",
        "changes_features": True,
        "apply": _already_past_cod,
    },
    "restudy": {
        "name": "restudy",
        "note": "If one additional restudy were on the record.",
        "changes_features": True,
        "apply": _restudy,
    },
    "rate_shock": {
        "name": "rate_shock",
        "note": "If observation interest rate were +2 points vs the row.",
        "changes_features": True,
        "apply": _rate_shock,
    },
    "serial_developer": {
        "name": "serial_developer",
        "note": "If sponsor prior withdrawal rate were at least 75%.",
        "changes_features": True,
        "apply": _serial_developer,
    },
    "high_system_delay": {
        "name": "high_system_delay",
        "note": "Pile crowding forced high. Electrum X unchanged; P(quit) delta is 0 unless you retrain with pile features.",
        "changes_features": False,
        "apply": _identity,
        "force_pile_crowded": True,
    },
}


def scenario_names() -> list[str]:
    return list(SCENARIOS.keys())


def apply_scenario(X: pd.DataFrame, name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    spec = SCENARIOS.get(name)
    if spec is None:
        raise KeyError(f"unknown scenario {name}; have {scenario_names()}")
    return spec["apply"](X), spec
