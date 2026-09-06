"""V1 modeling feature policy: default drops, reference dummies, ablation packs.

Does not fit models. Policy is derived from train `model_ready` + schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import GOLD_DIR, QUALITY_DIR

MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_DIR = MODELING_DIR / "artifacts"
REPORT_DIR = QUALITY_DIR / "modeling"

META = {"project_key", "observation_date", "withdraw_next_12m"}

# Always drop from V1 default X
HARD_DROPS = [
    "capacity_mw",  # keep log1p_capacity_mw
    "technology_primary_missing",  # constant 0 on train
    "state_code_missing",  # constant 0 on train
    "years_since_last_change",
    "years_since_last_change_missing",
]

# Prefer these as one-hot reference levels when present (else most-frequent train level)
PREFERRED_REF = {
    "technology_primary": "technology_primary__OTHER_RARE",
    "state_code": "state_code__OTHER_RARE",
}

DPP_FAMILY_PREFIXES = (
    "network_upgrade_cost",
    "study_delay_days",
    "restudy_count",
    "upgrade_cost_per_mw",
    "capacity_reduction_pct",
    "cost_change_since_previous_study",
    "dpp_event_count_to_date",
    "dpp_delay_info_available",
)

MACRO_FAMILY = [
    "construction_cost_index_change_12m",
    "interest_rate_at_entry",
    "interest_rate_at_observation",
    "interest_rate_change_since_entry",
    "miso_demand_yoy_pct",
    "miso_generation_yoy_pct",
    "miso_mean_demand_mw",
    "miso_net_interchange_mw",
    "miso_peak_demand_mw",
    # System-wide year-grain signals (not project-local)
    "prior_12m_withdrawal_count",
    "avg_withdrawn_mw_12m",
]


def _x_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META]


def _onehot_groups(cols: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for c in cols:
        if "__" in c:
            cat = c.split("__", 1)[0]
            groups.setdefault(cat, []).append(c)
    return groups


def _pick_reference_dummy(train: pd.DataFrame, dummies: list[str], preferred: str | None) -> str | None:
    present = [c for c in dummies if c in train.columns]
    if not present:
        return None
    if preferred and preferred in present:
        return preferred
    # Most frequent positive rate on train
    rates = {c: float(pd.to_numeric(train[c], errors="coerce").fillna(0).mean()) for c in present}
    return max(rates, key=rates.get)


def _dpp_family_cols(cols: list[str]) -> list[str]:
    out = []
    for c in cols:
        for p in DPP_FAMILY_PREFIXES:
            if c == p or c.startswith(p + "_"):
                out.append(c)
                break
    return out


def build_v1_feature_policy(
    train: pd.DataFrame,
    schema: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Compute V1 feature columns, drops, reference dummies, and ablation packs."""
    all_x = _x_columns(train)
    drops: list[str] = []
    notes: list[str] = []

    for c in HARD_DROPS:
        if c in all_x:
            drops.append(c)

    # Any other constant indicators on train
    for c in all_x:
        if c in drops:
            continue
        if c.endswith("_missing") or c.endswith("_available"):
            if int(pd.to_numeric(train[c], errors="coerce").nunique(dropna=True)) <= 1:
                drops.append(c)
                notes.append(f"Dropped constant indicator `{c}` on train.")

    # Reference dummies for full-rank one-hot groups
    ref_drops: dict[str, str] = {}
    groups = _onehot_groups(all_x)
    for cat, dummies in groups.items():
        # study_phase / service_type also have *_missing — drop a level ref, keep missing
        preferred = PREFERRED_REF.get(cat)
        # For cats with missing indicator, exclude *_missing from dummy list for ref pick
        level_dummies = [d for d in dummies if not d.endswith("_missing")]
        ref = _pick_reference_dummy(train, level_dummies, preferred)
        if ref:
            ref_drops[cat] = ref
            if ref not in drops:
                drops.append(ref)

    drops = list(dict.fromkeys(drops))  # stable unique
    v1_cols = [c for c in all_x if c not in drops]

    # Ablation packs
    years_cols = [c for c in all_x if c.startswith("years_since_last_change")]
    dpp_cols = _dpp_family_cols(all_x)
    macro_cols = [c for c in MACRO_FAMILY if c in all_x]

    ablation = {
        "ablation_years_since_last_change": {
            "action": "add_to_v1",
            "columns": years_cols,
            "note": "Default excluded (~97.7% missing). Model A = V1+these; Model B = V1.",
        },
        "ablation_dpp_family": {
            "action": "remove_from_v1",
            "columns": [c for c in dpp_cols if c in v1_cols],
            "note": "Keep in V1 by default; ablate entire DPP cost/delay/restudy family.",
        },
        "ablation_macro_family": {
            "action": "remove_from_v1",
            "columns": [c for c in macro_cols if c in v1_cols],
            "note": "Includes FRED/EIA macros and system-wide prior_12m_* year-grain signals.",
        },
        "ablation_with_capacity_mw": {
            "action": "add_to_v1",
            "columns": ["capacity_mw"] if "capacity_mw" in all_x else [],
            "note": "Sanity: V1 uses log1p_capacity_mw only; add raw capacity_mw back if needed.",
        },
    }

    verification = {
        "restudy_count": (
            "Among non-null train values only {0,1} appear (mostly 0). Effectively an "
            "'any restudy in eligible DPP history' flag, not a rich multi-restudy count."
        ),
        "nearby_transmission_voltage": (
            "Nine discrete kV classes (115–765). Ordered discrete; OK as numeric continuous proxy."
        ),
        "prior_12m_withdrawal_count": (
            "Only 3 unique values on train (= observation years). Built in build_training.py as "
            "system-wide queue withdrawals in (t-12m, t], not project-local. Year-grain market signal; "
            "included in ablation_macro_family."
        ),
        "avg_withdrawn_mw_12m": (
            "Derived as prior_12m_withdrawn_mw / prior_12m_withdrawal_count; inherits same 3-year grain."
        ),
        "onehot_reference": (
            "Dropped one reference dummy per categorical group for unregularized logistic "
            f"(refs: {ref_drops})."
        ),
    }

    policy = {
        "name": "v1",
        "n_all_x": len(all_x),
        "n_v1": len(v1_cols),
        "feature_columns_v1": v1_cols,
        "dropped_from_default": drops,
        "reference_dummies_dropped": ref_drops,
        "hard_drops": [c for c in HARD_DROPS if c in all_x],
        "ablation_packs": ablation,
        "verification_notes": verification,
        "extra_notes": notes,
        "fit_note": (
            "Imputer/scaler fitted on full model_ready train X; V1 matrices are column subsets "
            "of logistic_ready_* / tree_ready_*."
        ),
    }
    return policy


def write_v1_policy(
    policy: dict[str, Any],
    artifacts_dir: Path | None = None,
    report_dir: Path | None = None,
) -> dict[str, str]:
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    report_dir = report_dir or REPORT_DIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = artifacts_dir / "feature_policy_v1.json"
    cols_path = artifacts_dir / "feature_columns_v1.json"
    md_path = report_dir / "feature_policy_v1.md"

    json_path.write_text(json.dumps(policy, indent=2, default=str), encoding="utf-8")
    cols_path.write_text(
        json.dumps(
            {
                "feature_columns": policy["feature_columns_v1"],
                "n": policy["n_v1"],
                "policy": "v1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Feature policy V1 (logistic / tree default X)",
        "",
        f"Default `X` columns: **{policy['n_v1']}** (from {policy['n_all_x']} model-ready features).",
        "",
        "## Default drops",
        "",
    ]
    for c in policy["dropped_from_default"]:
        lines.append(f"- `{c}`")
    lines.extend(["", "## Reference dummies dropped (dummy trap)", ""])
    for cat, ref in (policy.get("reference_dummies_dropped") or {}).items():
        lines.append(f"- `{cat}` → drop `{ref}`")
    lines.extend(["", "## Ablation packs", ""])
    for name, pack in (policy.get("ablation_packs") or {}).items():
        lines.append(f"### `{name}`")
        lines.append(f"- Action: `{pack['action']}`")
        lines.append(f"- Note: {pack['note']}")
        lines.append(f"- Columns ({len(pack['columns'])}): " + ", ".join(f"`{c}`" for c in pack["columns"][:20]))
        if len(pack["columns"]) > 20:
            lines.append(f"  … +{len(pack['columns']) - 20} more")
        lines.append("")
    lines.extend(["", "## Verification notes", ""])
    for k, v in (policy.get("verification_notes") or {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.extend(["", f"Artifacts: `{json_path}`, `{cols_path}`", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"policy_json": str(json_path), "columns_json": str(cols_path), "md": str(md_path)}
