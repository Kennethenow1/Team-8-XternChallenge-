"""Build project master, snapshots, and inter-observation change features."""

from __future__ import annotations

import pandas as pd

from src.common.canonical_schema import MASTER_COLUMNS, SNAPSHOT_CORE_COLUMNS, SNAPSHOT_NATURAL_KEY
from src.common.paths import SILVER_DIR, QUALITY_DIR, ensure_layer_dirs
from src.silver.crosswalk import apply_project_keys, build_crosswalk


def _load_all_projects() -> pd.DataFrame:
    frames = []
    for name in ("berkeley_all.parquet", "miso_all.parquet"):
        path = SILVER_DIR / "projects" / name
        if path.exists():
            frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError("No silver project files found")
    return pd.concat(frames, ignore_index=True, sort=False)


def add_change_features(snaps: pd.DataFrame) -> pd.DataFrame:
    snaps = snaps.sort_values(["project_key", "observation_date", "source_name"]).copy()
    g = snaps.groupby("project_key", sort=False)

    snaps["previous_status"] = g["status_clean"].shift(1)
    snaps["previous_capacity_mw"] = g["capacity_mw"].shift(1)
    snaps["previous_service_date"] = g["proposed_service_date"].shift(1)
    snaps["previous_observation_date"] = g["observation_date"].shift(1)

    prev_cap = pd.to_numeric(snaps["previous_capacity_mw"], errors="coerce")
    cur_cap = pd.to_numeric(snaps["capacity_mw"], errors="coerce")
    snaps["capacity_change_mw"] = cur_cap - prev_cap
    snaps["capacity_change_pct"] = (100.0 * (cur_cap - prev_cap) / prev_cap).where(prev_cap.notna() & (prev_cap != 0))
    # Leave missing when previous observation unavailable — do not treat as 0

    def _month_delta(a, b):
        if pd.isna(a) or pd.isna(b):
            return pd.NA
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        return (a.year - b.year) * 12 + (a.month - b.month)

    snaps["service_date_shift_months"] = [
        _month_delta(a, b)
        for a, b in zip(snaps["proposed_service_date"], snaps["previous_service_date"], strict=False)
    ]
    snaps["status_changed"] = (
        snaps["previous_status"].notna() & (snaps["status_clean"] != snaps["previous_status"])
    )
    snaps["years_in_queue"] = (
        (pd.to_datetime(snaps["observation_date"]) - pd.to_datetime(snaps["queue_date"])).dt.days / 365.25
    )
    snaps["time_since_previous_observation"] = (
        pd.to_datetime(snaps["observation_date"]) - pd.to_datetime(snaps["previous_observation_date"])
    ).dt.days / 365.25
    snaps["missing_previous_observation"] = snaps["previous_observation_date"].isna()
    return snaps


def build_master_and_snapshots() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_layer_dirs()
    cross_path = SILVER_DIR / "crosswalks" / "project_crosswalk.parquet"
    if cross_path.exists():
        cross = pd.read_parquet(cross_path)
    else:
        cross = build_crosswalk()

    projects = _load_all_projects()
    projects = apply_project_keys(projects, cross)

    # Snapshots: one row per project_key × observation_date × source_name
    cols = [c for c in SNAPSHOT_CORE_COLUMNS if c in projects.columns]
    snaps = projects[cols].copy()
    # Drop exact natural-key duplicates (keep highest quality_score)
    snaps["quality_score"] = pd.to_numeric(snaps["quality_score"], errors="coerce")
    snaps = snaps.sort_values("quality_score", ascending=False)
    dup_mask = snaps.duplicated(SNAPSHOT_NATURAL_KEY, keep="first")
    n_dup = int(dup_mask.sum())
    if n_dup:
        (QUALITY_DIR / "snapshot_duplicate_keys.csv").write_text(
            snaps.loc[dup_mask, SNAPSHOT_NATURAL_KEY].to_csv(index=False), encoding="utf-8"
        )
        print(f"WARNING: {n_dup} duplicate snapshot keys dropped (kept highest quality_score)")
    snaps = snaps.loc[~dup_mask].copy()

    # Integrity: natural key unique
    assert not snaps.duplicated(SNAPSHOT_NATURAL_KEY).any(), "Snapshot natural key not unique"

    snaps = add_change_features(snaps)
    snaps.to_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet", index=False)

    # Master: stable identity — first non-null across time, no mutable status/capacity/service dates
    snaps_sorted = snaps.sort_values("observation_date")
    master_rows = []
    for key, grp in snaps_sorted.groupby("project_key"):
        def first_valid(col):
            s = grp[col].dropna()
            return s.iloc[0] if len(s) else None

        master_rows.append(
            {
                "project_key": key,
                "queue_date": first_valid("queue_date"),
                "technology_primary": first_valid("technology_primary"),
                "technology_secondary": first_valid("technology_secondary"),
                "state": first_valid("state"),
                "state_code": first_valid("state_code"),
                "county_fips": first_valid("county_fips"),
                "poi_key": first_valid("poi_key"),
                "first_observed_date": grp["observation_date"].min(),
                "last_observed_date": grp["observation_date"].max(),
            }
        )
    master = pd.DataFrame(master_rows)[MASTER_COLUMNS]
    master.to_parquet(SILVER_DIR / "projects" / "project_master.parquet", index=False)
    print(f"master={len(master)} snapshots={len(snaps)}")
    return master, snaps


if __name__ == "__main__":
    build_master_and_snapshots()
