"""Top-model feature ablation specs and column join helpers (val-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.modeling.feature_policy import MACRO_FAMILY
from src.modeling.model_registry import ARTIFACTS_DIR, MODELING_DIR

MACRO_FRED = [
    "construction_cost_index_change_12m",
    "interest_rate_at_entry",
    "interest_rate_at_observation",
    "interest_rate_change_since_entry",
]

MACRO_EIA = [
    "miso_demand_yoy_pct",
    "miso_generation_yoy_pct",
    "miso_mean_demand_mw",
    "miso_net_interchange_mw",
    "miso_peak_demand_mw",
]

MACRO_SYSTEM = [
    "prior_12m_withdrawal_count",
    "avg_withdrawn_mw_12m",
]

POLICY_JSON = ARTIFACTS_DIR / "feature_policy_v1.json"
READY_PREFIX = "logistic_ready"


def load_feature_policy_v1() -> dict[str, Any]:
    if POLICY_JSON.exists():
        return json.loads(POLICY_JSON.read_text(encoding="utf-8"))
    from src.modeling.feature_policy import build_v1_feature_policy

    train_path = MODELING_DIR / "model_ready_train.parquet"
    if not train_path.exists():
        train_path = MODELING_DIR / f"{READY_PREFIX}_train.parquet"
    train = pd.read_parquet(train_path)
    return build_v1_feature_policy(train)


def _ready_path(split: str) -> Path:
    for prefix in (READY_PREFIX, "model_ready"):
        p = MODELING_DIR / f"{prefix}_{split}.parquet"
        if p.exists():
            return p
    raise FileNotFoundError(f"No ready matrix for split={split!r}")


def join_extra_feature_columns(
    X: pd.DataFrame,
    meta: pd.DataFrame,
    columns: Sequence[str],
    split: str,
) -> tuple[pd.DataFrame, list[str], str | None]:
    """Join requested columns from logistic_ready / model_ready onto X via meta keys."""
    want = [c for c in columns if c not in X.columns]
    if not want:
        return X, [], None

    ready = pd.read_parquet(_ready_path(split))
    keys = [c for c in ("project_key", "observation_date") if c in meta.columns and c in ready.columns]
    if len(keys) < 2:
        return X, [], f"cannot join {want}: missing project_key/observation_date on meta"

    avail = [c for c in want if c in ready.columns]
    missing = [c for c in want if c not in ready.columns]
    if not avail:
        return X, [], f"columns not in ready matrix: {missing}"

    left = meta[keys].copy()
    left["observation_date"] = pd.to_datetime(left["observation_date"])
    sub = ready[keys + avail].copy()
    sub["observation_date"] = pd.to_datetime(sub["observation_date"])
    merged = left.merge(sub, on=keys, how="left", validate="many_to_one")
    out = X.copy()
    for c in avail:
        out[c] = pd.to_numeric(merged[c], errors="coerce") if c != "years_since_last_change_missing" else merged[c]
        if c == "years_since_last_change" and "years_since_last_change_missing" in want and "years_since_last_change_missing" not in avail:
            out["years_since_last_change_missing"] = out["years_since_last_change"].isna().astype(float)

    note = None
    if missing:
        note = f"partial join; missing in ready matrix: {missing}"
    return out, avail, note


def _pack_cols(policy: dict[str, Any], pack_name: str) -> list[str]:
    packs = policy.get("ablation_packs") or {}
    pack = packs.get(pack_name) or {}
    return list(pack.get("columns") or [])


@dataclass(frozen=True)
class AblationSpec:
    name: str
    drop_cols: tuple[str, ...] = ()
    add_cols: tuple[str, ...] = ()
    description: str = ""


def build_ablation_specs(policy: dict[str, Any] | None = None) -> list[AblationSpec]:
    policy = policy or load_feature_policy_v1()
    dpp = _pack_cols(policy, "ablation_dpp_family")
    years = _pack_cols(policy, "ablation_years_since_last_change")
    cap = _pack_cols(policy, "ablation_with_capacity_mw")

    return [
        AblationSpec("v1_full", description="Default V1 feature set"),
        AblationSpec(
            "v1_minus_macro",
            drop_cols=tuple(MACRO_FAMILY),
            description="Drop full macro family (FRED + EIA + system-wide)",
        ),
        AblationSpec(
            "v1_minus_dpp",
            drop_cols=tuple(dpp),
            description="Drop DPP cost/delay/restudy family",
        ),
        AblationSpec(
            "v1_plus_years_since_last_change",
            add_cols=tuple(years),
            description="Add years_since_last_change (+ missing indicator if available)",
        ),
        AblationSpec(
            "v1_plus_capacity_mw",
            add_cols=tuple(cap),
            description="Add raw capacity_mw alongside log1p_capacity_mw",
        ),
        AblationSpec(
            "v1_minus_macro_fred",
            drop_cols=tuple(MACRO_FRED),
            description="Drop FRED macro columns only",
        ),
        AblationSpec(
            "v1_minus_macro_eia",
            drop_cols=tuple(MACRO_EIA),
            description="Drop EIA/MISO macro columns only",
        ),
        AblationSpec(
            "v1_minus_macro_system",
            drop_cols=tuple(MACRO_SYSTEM),
            description="Drop system-wide prior_12m_* + avg_withdrawn_mw_12m",
        ),
    ]


METRIC_KEYS = (
    "pr_auc",
    "roc_auc",
    "brier",
    "ece",
    "log_loss",
    "precision_at_10pct",
    "recall_at_10pct",
    "lift_at_10pct",
    "withdrawn_mw_capture_at_10pct",
    "best_iteration",
    "n_features",
)
