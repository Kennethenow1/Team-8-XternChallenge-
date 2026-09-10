"""Build Gold delay panel, survival-COD intervals, and split_manifest.

Does not replace withdrawal gold. Parallel tables under data/gold/delay/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, SILVER_DIR, QUALITY_DIR, ensure_layer_dirs
from src.gold.build_training import FEATURE_MANIFEST, engineer_pit_features
from src.gold.cod_delay import (
    DELAY_OUTCOME_COLUMNS,
    FOLLOWUP_MONTHS,
    assign_delay_labels,
    audit_label_counts,
    calendar_split,
    is_gia_row,
    load_eia_matched,
    load_outcomes,
    load_snapshots,
)

DELAY_DIR = GOLD_DIR / "delay"
PROMOTE = [
    "transmission_owner",
    "transmission_owner_clean",
    "post_gia_status",
    "study_cycle",
    "study_group",
    "dp1_eris_mw",
    "dp1_nris_mw",
    "dp2_eris_mw",
    "dp2_nris_mw",
    "poi_name",
]


def _annual_active(snaps: pd.DataFrame) -> pd.DataFrame:
    feat = engineer_pit_features(snaps)
    extra = [c for c in PROMOTE if c in feat.columns]
    keep_src = [
        "project_key",
        "observation_date",
        "published_at",
        "source_name",
        "source_id",
        "source_project_id",
        "status_clean",
        "queue_date",
        "withdrawal_date",
        "study_phase",
        "service_type",
        "technology_primary",
        "is_hybrid",
        "state_code",
        "county_fips",
        "poi_key",
        *FEATURE_MANIFEST,
        *extra,
    ]
    cols = [c for c in keep_src if c in feat.columns]
    active = feat[feat["status_clean"] == "active"][cols].copy()
    active["_src_rank"] = np.where(active["source_name"].eq("Berkeley"), 0, 1)
    active["_year"] = pd.to_datetime(active["observation_date"]).dt.year
    active = active.sort_values(["project_key", "_year", "_src_rank", "observation_date"]).drop_duplicates(
        ["project_key", "_year"], keep="first"
    )
    return active.drop(columns=["_src_rank"], errors="ignore")


def _join_project_promote(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for name in ("berkeley_all.parquet", "miso_all.parquet"):
        path = SILVER_DIR / "projects" / name
        if path.exists():
            frames.append(pd.read_parquet(path))
    if not frames:
        return panel
    parts = []
    for fr in frames:
        cols = [c for c in ["project_key", "observation_date", *PROMOTE] if c in fr.columns]
        parts.append(fr[cols])
    proj = pd.concat(parts, ignore_index=True, sort=False)
    proj["observation_date"] = pd.to_datetime(proj["observation_date"], errors="coerce")
    use = [c for c in ["project_key", "observation_date", *PROMOTE] if c in proj.columns]
    proj = proj[use].drop_duplicates(["project_key", "observation_date"], keep="last")
    out = panel.copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    merged = out.merge(proj, on=["project_key", "observation_date"], how="left", suffixes=("", "_proj"))
    for c in PROMOTE:
        src = f"{c}_proj"
        if src in merged.columns:
            if c not in merged.columns:
                merged[c] = merged[src]
            else:
                merged[c] = merged[c].where(merged[c].notna(), merged[src])
            merged = merged.drop(columns=[src], errors="ignore")
        elif c not in merged.columns:
            merged[c] = pd.NA
    return merged


def _join_enriched(panel: pd.DataFrame) -> pd.DataFrame:
    path = GOLD_DIR / "withdrawal_panel_enriched.parquet"
    if not path.exists():
        return panel
    enr = pd.read_parquet(path)
    enr["observation_date"] = pd.to_datetime(enr["observation_date"])
    drop_labels = [c for c in ("withdraw_next_12m", "next_outcome") if c in enr.columns]
    extra = [c for c in enr.columns if c not in set(panel.columns) and c not in drop_labels]
    keys = ["project_key", "observation_date"]
    add = enr[keys + extra].copy()
    # Never leak withdrawal labels into delay X
    out = panel.merge(add, on=keys, how="left")
    return out


def _join_dpp_mtep_if_missing(panel: pd.DataFrame) -> pd.DataFrame:
    """If enrichment join did not bring DPP/MTEP, leave columns as NA (do not invent)."""
    out = panel.copy()
    for c in (
        "network_upgrade_cost",
        "upgrade_cost_per_mw",
        "study_delay_days",
        "restudy_count",
        "nearby_mtep_upgrade_count",
        "mtep_investment_nearby_usd",
        "dpp_delay_info_available",
    ):
        if c not in out.columns:
            out[c] = pd.NA
    return out


def build_survival_cod(snaps: pd.DataFrame, outcomes: pd.DataFrame, delay_panel: pd.DataFrame) -> pd.DataFrame:
    feat = engineer_pit_features(snaps).sort_values(["project_key", "observation_date"])
    feat["observation_date"] = pd.to_datetime(feat["observation_date"])
    oc = outcomes.copy() if len(outcomes) else pd.DataFrame()
    if len(oc):
        oc["outcome_date"] = pd.to_datetime(oc["outcome_date"], errors="coerce")
        oc = oc.drop_duplicates("project_key", keep="first")
        oc_map = oc.set_index("project_key")
    else:
        oc_map = None

    num_cols = [c for c in FEATURE_MANIFEST if c in feat.columns]
    rows: list[dict] = []
    for key, grp in feat.groupby("project_key", sort=False):
        grp = grp.reset_index(drop=True)
        outcome_type = None
        outcome_date = pd.NaT
        if oc_map is not None and key in oc_map.index:
            outcome_type = oc_map.loc[key, "outcome_type"]
            outcome_date = pd.to_datetime(oc_map.loc[key, "outcome_date"], errors="coerce")
        for i in range(len(grp)):
            start = pd.Timestamp(grp.loc[i, "observation_date"])
            stop = (
                pd.Timestamp(grp.loc[i + 1, "observation_date"])
                if i + 1 < len(grp)
                else start + pd.DateOffset(months=12)
            )
            withdrawal_event = 0
            operation_event = 0
            if pd.notna(outcome_date) and start < outcome_date <= stop:
                if outcome_type == "withdrawn":
                    withdrawal_event = 1
                    stop = outcome_date
                elif outcome_type in {"operational", "completed"}:
                    operation_event = 1
                    stop = outcome_date
            row = {
                "project_key": key,
                "start_date": start,
                "stop_date": stop,
                "withdrawal_event": withdrawal_event,
                "operation_event": operation_event,
            }
            for c in num_cols:
                row[c] = grp.loc[i, c]
            rows.append(row)
    surv = pd.DataFrame(rows)
    DELAY_DIR.mkdir(parents=True, exist_ok=True)
    surv.to_parquet(DELAY_DIR / "survival_cod_training.parquet", index=False)
    return surv


def write_split_manifest(panel: pd.DataFrame, audit: dict) -> None:
    labeled = panel["cod_slip_months_next_12m"].notna()
    manifest = {
        "task": "cod_slip_months_next_12m",
        "companion": "cod_slip_ge_12m",
        "train_years": [2020, 2021, 2022],
        "validation_year": 2023,
        "test_year": 2024,
        "score_years": [2025, 2026],
        "followup_months": FOLLOWUP_MONTHS,
        "counts_by_split": panel["split"].value_counts().to_dict(),
        "labeled_by_split": panel.loc[labeled, "split"].value_counts().to_dict(),
        "complete_followup_by_split": panel.groupby("split")["complete_followup"].mean().astype(float).to_dict(),
        "neural_nets_ok": audit.get("neural_nets_ok"),
        "excluded_outcome_columns": list(DELAY_OUTCOME_COLUMNS),
        "note": audit.get("note"),
        "audit": {k: audit[k] for k in ("val_labeled", "train_labeled", "gia_val_labeled", "neural_nets_ok") if k in audit},
    }
    (DELAY_DIR / "split_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def build_delay_gold() -> dict[str, pd.DataFrame]:
    ensure_layer_dirs()
    DELAY_DIR.mkdir(parents=True, exist_ok=True)
    snaps = load_snapshots()
    outcomes = load_outcomes()
    eia = load_eia_matched()
    annual = _annual_active(snaps)
    annual = _join_project_promote(annual)
    labeled = assign_delay_labels(annual, snaps, outcomes, followup_months=FOLLOWUP_MONTHS, eia=eia)
    labeled = labeled.loc[:, ~labeled.columns.duplicated()].copy()
    labeled["split"] = calendar_split(pd.to_datetime(labeled["observation_date"]).dt.year)
    sp = labeled["study_phase"] if "study_phase" in labeled.columns else pd.Series(pd.NA, index=labeled.index)
    pg = labeled["post_gia_status"] if "post_gia_status" in labeled.columns else pd.Series(pd.NA, index=labeled.index)
    if isinstance(sp, pd.DataFrame):
        sp = sp.iloc[:, 0]
    if isinstance(pg, pd.DataFrame):
        pg = pg.iloc[:, 0]
    labeled["is_gia"] = [is_gia_row(a, b) for a, b in zip(sp.to_numpy(), pg.to_numpy(), strict=False)]
    labeled = _join_enriched(labeled)
    labeled = _join_dpp_mtep_if_missing(labeled)
    # Drop withdrawal labels if they leaked from enrichment
    labeled = labeled.drop(columns=["withdraw_next_12m", "next_outcome"], errors="ignore")

    out_path = DELAY_DIR / "cod_delay_panel.parquet"
    labeled.to_parquet(out_path, index=False)
    labeled.to_csv(DELAY_DIR / "cod_delay_panel.csv", index=False)

    surv = build_survival_cod(snaps, outcomes, labeled)
    audit = audit_label_counts(labeled)
    write_split_manifest(labeled, audit)
    (DELAY_DIR / "label_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    report_dir = QUALITY_DIR / "modeling"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "cod_delay_label_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    print(
        f"delay panel={len(labeled)} labeled={int(labeled['cod_slip_months_next_12m'].notna().sum())} "
        f"val_labeled={audit['val_labeled']} neural_nets_ok={audit['neural_nets_ok']} survival={len(surv)}"
    )
    return {"panel": labeled, "survival": surv, "audit": audit}


if __name__ == "__main__":
    build_delay_gold()
