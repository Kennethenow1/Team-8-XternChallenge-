"""Separate outcome table — never used as a feature source accidentally."""

from __future__ import annotations

import pandas as pd

from src.common.paths import SILVER_DIR, ensure_layer_dirs


def build_outcomes(snaps: pd.DataFrame | None = None) -> pd.DataFrame:
    ensure_layer_dirs()
    if snaps is None:
        snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")

    snaps = snaps.sort_values(["project_key", "observation_date"]).copy()
    rows = []

    for key, grp in snaps.groupby("project_key"):
        grp = grp.reset_index(drop=True)
        statuses = grp["status_clean"].tolist()
        obs_dates = pd.to_datetime(grp["observation_date"])
        wd_dates = pd.to_datetime(grp["withdrawal_date"])
        op_dates = pd.to_datetime(grp["operational_date"])
        done_dates = pd.to_datetime(grp["completion_date"]) if "completion_date" in grp.columns else pd.Series([pd.NaT] * len(grp))

        last_active = None
        first_withdrawn = None
        for i, st in enumerate(statuses):
            if st == "active":
                last_active = obs_dates.iloc[i]
            if st == "withdrawn" and first_withdrawn is None:
                first_withdrawn = obs_dates.iloc[i]

        # Prefer explicit withdrawal_date when present
        explicit_wd = wd_dates.dropna()
        explicit_op = op_dates.dropna()
        explicit_done = done_dates.dropna()

        outcome_type = "unknown"
        outcome_date = pd.NaT
        outcome_precision = None
        confidence = "low"
        source = None

        if len(explicit_wd):
            outcome_type = "withdrawn"
            outcome_date = explicit_wd.iloc[0]
            outcome_precision = "day"
            confidence = "high"
            source = grp.loc[explicit_wd.index[0], "source_name"]
        elif "withdrawn" in statuses:
            outcome_type = "withdrawn"
            # Interval: last_known_active < true wd <= first_known_withdrawn
            outcome_date = first_withdrawn
            outcome_precision = "interval"
            confidence = "medium"
            source = grp.loc[statuses.index("withdrawn"), "source_name"]
        elif len(explicit_op) or "operational" in statuses:
            outcome_type = "operational"
            outcome_date = explicit_op.iloc[0] if len(explicit_op) else obs_dates.iloc[statuses.index("operational")]
            outcome_precision = "day" if len(explicit_op) else "observation"
            confidence = "high" if len(explicit_op) else "medium"
            source = grp.iloc[-1]["source_name"]
        elif len(explicit_done) or "completed" in statuses:
            # Completed/Done is not automatically operational
            outcome_type = "completed"
            outcome_date = explicit_done.iloc[0] if len(explicit_done) else obs_dates.iloc[-1]
            outcome_precision = "day" if len(explicit_done) else "observation"
            confidence = "medium"
            source = grp.iloc[-1]["source_name"]
        elif statuses and statuses[-1] == "active":
            outcome_type = "active_censored"
            outcome_date = obs_dates.iloc[-1]
            outcome_precision = "observation"
            confidence = "high"
            source = grp.iloc[-1]["source_name"]
        elif statuses and statuses[-1] == "suspended":
            outcome_type = "unknown"
            outcome_date = obs_dates.iloc[-1]
            outcome_precision = "observation"
            confidence = "low"
            source = grp.iloc[-1]["source_name"]

        rows.append(
            {
                "project_key": key,
                "outcome_type": outcome_type,
                "outcome_date": outcome_date,
                "outcome_date_precision": outcome_precision,
                "last_known_active_date": last_active,
                "first_known_withdrawn_date": first_withdrawn,
                "outcome_source": source,
                "outcome_confidence": confidence,
            }
        )

    outcomes = pd.DataFrame(rows)
    outcomes.to_parquet(SILVER_DIR / "outcomes" / "project_outcomes.parquet", index=False)
    outcomes.to_csv(SILVER_DIR / "outcomes" / "project_outcomes.csv", index=False)
    print(outcomes["outcome_type"].value_counts().to_dict())
    return outcomes


if __name__ == "__main__":
    build_outcomes()
