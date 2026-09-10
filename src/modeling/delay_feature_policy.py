"""Delay-task feature policy. Independent of withdrawal V1."""

from __future__ import annotations

from typing import Any

NATIVE_CATEGORICALS = (
    "technology_primary",
    "state_code",
    "study_phase",
    "service_type",
    "transmission_owner",
    "post_gia_status",
    "study_cycle",
)

META = {
    "project_key",
    "observation_date",
    "cod_slip_months_next_12m",
    "cod_slip_ge_12m",
    "event_type",
    "complete_followup",
    "capacity_mw",
    "split",
    "future_cod",
    "future_cod_obs",
    "cod_at_t",
    "cod_at_entry",
    "delay_from_original_months",
    "followup_months",
    "is_gia",
    "eia_future_cod_used",
    "published_at",
    "source_name",
    "source_id",
    "source_project_id",
    "status_clean",
    "queue_date",
    "withdrawal_date",
    "never_in_training",
    "project_last_obs",
    "horizon_date",
}

LEAK_PREFIXES = (
    "future_cod",
    "withdraw_next",
    "next_outcome",
    "outcome_",
)

HARD_DROPS = [
    "capacity_mw",  # keep log1p_capacity_mw when present
    "years_since_last_change",
]

NUMERIC_CANDIDATES = [
    "queue_age_months",
    "log1p_capacity_mw",
    "is_hybrid",
    "months_until_service",
    "service_date_passed",
    "capacity_change_pct",
    "service_date_shift_months",
    "other_active_projects_same_state",
    "other_active_mw_same_state",
    "other_active_projects_same_poi",
    "other_active_mw_same_poi",
    "other_active_mw_same_technology",
    "prior_12m_withdrawal_count",
    "prior_12m_withdrawn_mw",
    "years_in_queue",
    "dp1_eris_mw",
    "dp1_nris_mw",
    "dp2_eris_mw",
    "dp2_nris_mw",
    "network_upgrade_cost",
    "upgrade_cost_per_mw",
    "study_delay_days",
    "restudy_count",
    "nearby_mtep_upgrade_count",
    "mtep_investment_nearby_usd",
    "dpp_delay_info_available",
    "same_poi_project_count",
    "nearby_queue_mw",
    "interest_rate_at_observation",
    "interest_rate_at_entry",
    "interest_rate_change_since_entry",
    "construction_cost_index_change_12m",
    "miso_demand_yoy_pct",
    "miso_mean_demand_mw",
]

SEQ_CHANNELS = [
    "queue_age_months",
    "log1p_capacity_mw",
    "months_until_service",
    "service_date_shift_months",
    "restudy_count",
    "upgrade_cost_per_mw",
    "study_delay_days",
]


def x_columns(df) -> list[str]:
    return [c for c in df.columns if c not in META and not str(c).startswith(LEAK_PREFIXES)]


def delay_feature_lists(df) -> dict[str, Any]:
    cats = [c for c in NATIVE_CATEGORICALS if c in df.columns]
    nums = [c for c in NUMERIC_CANDIDATES if c in df.columns]
    # keep extra numeric extras that are not ids
    extra = []
    for c in df.columns:
        if c in META or c in cats or c in nums:
            continue
        if str(c).startswith(LEAK_PREFIXES):
            continue
        if df[c].dtype.kind in "biufc":
            extra.append(c)
    nums = list(dict.fromkeys(nums + extra))
    for d in HARD_DROPS:
        if d in nums:
            nums.remove(d)
    return {"categorical_columns": cats, "numeric_columns": nums, "feature_columns": cats + nums}
