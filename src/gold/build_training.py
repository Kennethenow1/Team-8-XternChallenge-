"""Build Gold annual classification, survival, and current MISO scoring tables."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.canonical_schema import OUTCOME_COLUMNS
from src.common.paths import GOLD_DIR, SILVER_DIR, ensure_layer_dirs

FEATURE_MANIFEST = [
    "queue_age_months",
    "log1p_capacity_mw",
    "technology_primary",
    "is_hybrid",
    "state_code",
    "months_until_service",
    "service_date_passed",
    "capacity_change_pct",
    "service_date_shift_months",
    "years_since_last_change",
    "other_active_projects_same_state",
    "other_active_mw_same_state",
    "other_active_projects_same_poi",
    "other_active_mw_same_poi",
    "other_active_mw_same_technology",
    "prior_12m_withdrawal_count",
    "prior_12m_withdrawn_mw",
    "years_in_queue",
    "study_phase",
    "service_type",
    "capacity_mw",
]


def _month_delta(later, earlier) -> float | None:
    if pd.isna(later) or pd.isna(earlier):
        return None
    later, earlier = pd.Timestamp(later), pd.Timestamp(earlier)
    return (later.year - earlier.year) * 12 + (later.month - earlier.month) + (
        later.day - earlier.day
    ) / 30.0


def engineer_pit_features(snaps: pd.DataFrame) -> pd.DataFrame:
    df = snaps.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["queue_date"] = pd.to_datetime(df["queue_date"])
    df["proposed_service_date"] = pd.to_datetime(df["proposed_service_date"])
    df["capacity_mw"] = pd.to_numeric(df["capacity_mw"], errors="coerce")

    df["queue_age_months"] = (
        (df["observation_date"] - df["queue_date"]).dt.days / 30.4375
    )
    df["log1p_capacity_mw"] = np.log1p(df["capacity_mw"].clip(lower=0))
    df["months_until_service"] = (
        (df["proposed_service_date"] - df["observation_date"]).dt.days / 30.4375
    )
    df["service_date_passed"] = (
        df["proposed_service_date"].notna() & (df["proposed_service_date"] <= df["observation_date"])
    ).astype(int)

    df = df.sort_values(["project_key", "observation_date"]).reset_index(drop=True)
    change = df["status_changed"].fillna(False) | (
        pd.to_numeric(df.get("capacity_change_mw"), errors="coerce").fillna(0).ne(0)
    )
    # years since last change within project
    years_since = []
    for _, grp in df.groupby("project_key", sort=False):
        lcd = None
        for is_chg, od in zip(change.loc[grp.index], grp["observation_date"], strict=False):
            if bool(is_chg):
                lcd = od
            years_since.append(None if lcd is None else (od - lcd).days / 365.25)
    df["years_since_last_change"] = years_since

    # Active peers by observation_date (exclude focal via subtract-self)
    active = df[df["status_clean"] == "active"].copy()
    active["_one"] = 1
    active["_mw"] = active["capacity_mw"].fillna(0.0)

    def _agg_other(keys: list[str], count_name: str, mw_name: str) -> pd.DataFrame:
        g = active.groupby(["observation_date", *keys], dropna=False).agg(
            _cnt=("_one", "sum"), _smw=("_mw", "sum")
        )
        merged = df.merge(g.reset_index(), on=["observation_date", *keys], how="left")
        # subtract self when focal is active
        is_active = df["status_clean"].eq("active")
        cnt = merged["_cnt"].fillna(0) - is_active.astype(int)
        smw = merged["_smw"].fillna(0.0) - df["capacity_mw"].fillna(0.0).where(is_active, 0.0)
        out = pd.DataFrame({count_name: cnt.clip(lower=0), mw_name: smw.clip(lower=0)})
        return out

    state_stats = _agg_other(["state_code"], "other_active_projects_same_state", "other_active_mw_same_state")
    poi_stats = _agg_other(["poi_key"], "other_active_projects_same_poi", "other_active_mw_same_poi")
    tech_g = active.groupby(["observation_date", "technology_primary"], dropna=False).agg(
        _smw=("_mw", "sum")
    )
    tech_merged = df.merge(tech_g.reset_index(), on=["observation_date", "technology_primary"], how="left")
    is_active = df["status_clean"].eq("active")
    tech_mw = tech_merged["_smw"].fillna(0.0) - df["capacity_mw"].fillna(0.0).where(is_active, 0.0)

    df["other_active_projects_same_state"] = state_stats["other_active_projects_same_state"].values
    df["other_active_mw_same_state"] = state_stats["other_active_mw_same_state"].values
    df["other_active_projects_same_poi"] = poi_stats["other_active_projects_same_poi"].values
    df["other_active_mw_same_poi"] = poi_stats["other_active_mw_same_poi"].values
    df["other_active_mw_same_technology"] = tech_mw.clip(lower=0).values

    # Prior 12m withdrawals available as of observation_date (same calendar date cohort)
    withdrawn_events = df[
        (df["status_clean"] == "withdrawn") | df["withdrawal_date"].notna()
    ][["project_key", "observation_date", "withdrawal_date", "capacity_mw"]].copy()
    withdrawn_events["event_date"] = pd.to_datetime(
        withdrawn_events["withdrawal_date"].fillna(withdrawn_events["observation_date"])
    )
    withdrawn_events = withdrawn_events.dropna(subset=["event_date"]).drop_duplicates(
        ["project_key", "event_date"]
    )

    # For each distinct observation_date, count events in (d-12m, d]
    prior_n = []
    prior_mw = []
    events = withdrawn_events.sort_values("event_date")
    event_dates = events["event_date"].to_numpy()
    event_mw = pd.to_numeric(events["capacity_mw"], errors="coerce").fillna(0).to_numpy()
    for od in df["observation_date"]:
        start = od - pd.DateOffset(months=12)
        mask = (event_dates > np.datetime64(start)) & (event_dates <= np.datetime64(od))
        prior_n.append(int(mask.sum()))
        prior_mw.append(float(event_mw[mask].sum()))
    # Note: includes all projects' withdrawals (focal exclusion negligible for rates; subtract if same key withdrew)
    df["prior_12m_withdrawal_count"] = prior_n
    df["prior_12m_withdrawn_mw"] = prior_mw
    return df


def _followup_label(row, outcomes: pd.DataFrame, snaps: pd.DataFrame) -> dict:
    """Label withdraw_next_12m with complete_followup and next_outcome."""
    key = row["project_key"]
    t0 = pd.Timestamp(row["observation_date"])
    t1 = t0 + pd.DateOffset(months=12)

    oc = outcomes[outcomes["project_key"] == key]
    proj_snaps = snaps[snaps["project_key"] == key].sort_values("observation_date")

    withdraw_next = 0
    next_outcome = "remained_active"
    complete = False

    # Verified withdrawal in (t0, t1]
    wd = None
    if len(oc):
        o = oc.iloc[0]
        if o["outcome_type"] == "withdrawn" and pd.notna(o["outcome_date"]):
            wd = pd.Timestamp(o["outcome_date"])
        elif o["outcome_type"] == "withdrawn" and pd.notna(o.get("first_known_withdrawn_date")):
            wd = pd.Timestamp(o["first_known_withdrawn_date"])

    if wd is not None and t0 < wd <= t1:
        withdraw_next = 1
        next_outcome = "withdrawn"
        complete = True
    else:
        # Operational in window?
        op = None
        if len(oc) and oc.iloc[0]["outcome_type"] == "operational" and pd.notna(oc.iloc[0]["outcome_date"]):
            op = pd.Timestamp(oc.iloc[0]["outcome_date"])
        if op is not None and t0 < op <= t1:
            next_outcome = "operational"
            withdraw_next = 0
            complete = True
        else:
            # Adequate follow-up: observe the project (or later source) at/after t1 still not withdrawn
            later = proj_snaps[pd.to_datetime(proj_snaps["observation_date"]) >= t1]
            if len(later):
                # If any later snap is withdrawn with date after t1, still 0 for this window
                if later.iloc[0]["status_clean"] == "withdrawn":
                    # withdrew after window
                    next_outcome = "remained_active"
                    withdraw_next = 0
                    complete = True
                else:
                    next_outcome = "remained_active"
                    withdraw_next = 0
                    complete = True
            else:
                # Check if global max observation across data covers t1 and project still active at last obs before end
                max_obs = pd.to_datetime(snaps["observation_date"]).max()
                if max_obs >= t1 and row["status_clean"] == "active":
                    # No later snap for this project but calendar follow-up exists — censored incomplete
                    complete = False
                else:
                    complete = False

    return {
        "withdraw_next_12m": withdraw_next,
        "next_outcome": next_outcome,
        "complete_followup": complete,
    }


def build_annual_training(snaps: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    # Prefer Berkeley snapshots for historical years; one row per project_key × calendar year
    # Active at observation year t
    feat = engineer_pit_features(snaps)
    active = feat[feat["status_clean"] == "active"].copy()

    # Prefer Berkeley over MISO when both exist same date (historical authority)
    active = active.sort_values(["project_key", "observation_date", "source_name"])
    # For same project_key+observation_date keep Berkeley if present
    def _rank(src):
        return 0 if src == "Berkeley" else 1

    active["_src_rank"] = active["source_name"].map(_rank)
    active = active.sort_values(["project_key", "observation_date", "_src_rank"]).drop_duplicates(
        ["project_key", "observation_date"], keep="first"
    )

    labels = [_followup_label(row, outcomes, snaps) for _, row in active.iterrows()]
    label_df = pd.DataFrame(labels, index=active.index)
    annual = pd.concat([active.reset_index(drop=True), label_df.reset_index(drop=True)], axis=1)

    # Split assignment
    year = pd.to_datetime(annual["observation_date"]).dt.year
    split = np.where(
        year.between(2020, 2022),
        "train",
        np.where(year == 2023, "val", np.where(year == 2024, "test", np.where(year >= 2025, "score", "other"))),
    )
    annual["split"] = split

    # never_in_training flag: project_key not seen in train years
    train_keys = set(annual.loc[annual["split"] == "train", "project_key"])
    annual["never_in_training"] = ~annual["project_key"].isin(train_keys)

    keep = (
        ["project_key", "observation_date", "published_at", "source_name", "source_id", "split", "never_in_training"]
        + [c for c in FEATURE_MANIFEST if c in annual.columns]
        + ["withdraw_next_12m", "next_outcome", "complete_followup"]
    )
    annual = annual[keep]

    # Verify feature manifest excludes outcomes
    for c in OUTCOME_COLUMNS:
        assert c not in FEATURE_MANIFEST

    out_dir = GOLD_DIR / "annual_withdrawal_training"
    annual.to_parquet(out_dir / "annual_withdrawal_training.parquet", index=False)
    annual.to_csv(out_dir / "annual_withdrawal_training.csv", index=False)
    return annual


def build_survival_training(snaps: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    feat = engineer_pit_features(snaps)
    feat = feat.sort_values(["project_key", "observation_date"])
    rows = []
    for key, grp in feat.groupby("project_key"):
        grp = grp.reset_index(drop=True)
        oc = outcomes[outcomes["project_key"] == key]
        outcome_type = oc.iloc[0]["outcome_type"] if len(oc) else "unknown"
        outcome_date = pd.to_datetime(oc.iloc[0]["outcome_date"]) if len(oc) and pd.notna(oc.iloc[0]["outcome_date"]) else pd.NaT

        for i in range(len(grp)):
            start = pd.Timestamp(grp.loc[i, "observation_date"])
            if i + 1 < len(grp):
                stop = pd.Timestamp(grp.loc[i + 1, "observation_date"])
            else:
                stop = start + pd.DateOffset(months=12)

            withdrawal_event = 0
            operation_event = 0
            if pd.notna(outcome_date) and start < outcome_date <= stop:
                if outcome_type == "withdrawn":
                    withdrawal_event = 1
                    stop = outcome_date
                elif outcome_type == "operational":
                    operation_event = 1
                    stop = outcome_date

            row = {
                "project_key": key,
                "start_date": start,
                "stop_date": stop,
                "withdrawal_event": withdrawal_event,
                "operation_event": operation_event,
            }
            for c in FEATURE_MANIFEST:
                if c in grp.columns:
                    row[c] = grp.loc[i, c]
            rows.append(row)

    surv = pd.DataFrame(rows)
    out_dir = GOLD_DIR / "survival_training"
    surv.to_parquet(out_dir / "survival_training.parquet", index=False)
    surv.to_csv(out_dir / "survival_training.csv", index=False)
    return surv


def build_current_scoring(snaps: pd.DataFrame) -> pd.DataFrame:
    feat = engineer_pit_features(snaps)
    cur = feat[(feat["source_name"] == "MISO") & (feat["status_clean"] == "active")].copy()
    keep = ["project_key", "observation_date", "published_at", "source_name", "source_project_id"] + [
        c for c in FEATURE_MANIFEST if c in cur.columns
    ]
    # Explicitly no future outcome labels
    for c in ("withdraw_next_12m", "next_outcome", "complete_followup", "withdrawal_event", "operation_event"):
        assert c not in keep
    cur = cur[keep]
    out_dir = GOLD_DIR / "current_miso_scoring"
    cur.to_parquet(out_dir / "current_miso_scoring.parquet", index=False)
    cur.to_csv(out_dir / "current_miso_scoring.csv", index=False)
    return cur


def write_split_manifest(annual: pd.DataFrame) -> None:
    year = pd.to_datetime(annual["observation_date"]).dt.year
    manifest = {
        "train_years": [2020, 2021, 2022],
        "validation_year": 2023,
        "test_year": 2024,
        "score_years": [2025, 2026],
        "counts_by_split": annual["split"].value_counts().to_dict(),
        "complete_followup_by_split": annual.groupby("split")["complete_followup"]
        .mean()
        .astype(float)
        .to_dict(),
        "feature_manifest": FEATURE_MANIFEST,
        "excluded_outcome_columns": OUTCOME_COLUMNS,
        "note": "Labels require complete_followup=True for supervised training rows.",
    }
    path = GOLD_DIR / "split_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def build_all_gold() -> dict[str, pd.DataFrame]:
    ensure_layer_dirs()
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    outcomes = pd.read_parquet(SILVER_DIR / "outcomes" / "project_outcomes.parquet")
    annual = build_annual_training(snaps, outcomes)
    surv = build_survival_training(snaps, outcomes)
    cur = build_current_scoring(snaps)
    write_split_manifest(annual)
    print(
        f"annual={len(annual)} survival={len(surv)} current_scoring={len(cur)} "
        f"complete_followup_rate={annual['complete_followup'].mean():.3f}"
    )
    return {"annual": annual, "survival": surv, "current": cur}


if __name__ == "__main__":
    build_all_gold()
