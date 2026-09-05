"""Standardize current MISO queue CSV into the canonical Silver schema."""

from __future__ import annotations

import pandas as pd

from src.bronze.ingest import load_registry_parquet
from src.common.canonical_schema import CANONICAL_COLUMNS
from src.common.normalize import (
    as_string_id,
    capacity_flags,
    clean_text,
    map_status,
    normalize_poi,
    normalize_state,
    parse_date_series,
    parse_technology_fields,
    quality_score_row,
    status_consistency,
    to_numeric_mw,
)
from src.common.paths import BRONZE_DIR, SILVER_DIR, ensure_layer_dirs


def standardize_miso_source(source: pd.Series) -> pd.DataFrame:
    path = BRONZE_DIR / source["bronze_subdir"] / source["source_file"]
    raw = pd.read_csv(path)
    n = len(raw)
    out = pd.DataFrame({c: [None] * n for c in CANONICAL_COLUMNS})

    out["source_project_id"] = as_string_id(raw["Project #"])
    out["source_name"] = "MISO"
    out["source_id"] = source["source_id"]
    out["source_file"] = source["source_file"]
    out["observation_date"] = pd.to_datetime(source["data_as_of_date"])
    out["published_at"] = pd.to_datetime(source["published_at"])

    date_map = {
        "queue_date": "Queue Date",
        "withdrawal_date": "Withdrawn Date",
        "completion_date": "Done Date",
        "proposed_service_date": "Negotiated In Service Date",
        "operational_date": "Appl In Service Date",
    }
    for prefix, col in date_map.items():
        series = raw[col] if col in raw.columns else pd.Series([None] * n)
        parsed = parse_date_series(series, prefix)
        for c in parsed.columns:
            out[c] = parsed[c].values

    st = map_status(raw["Request Status"], "miso")
    out["status_raw"] = st["status_raw"].values
    out["status_clean"] = st["status_clean"].values
    out["status"] = st["status"].values
    out["status_consistency_flag"] = status_consistency(
        out["status_clean"], out["withdrawal_date"], out["operational_date"]
    ).values

    summer = to_numeric_mw(raw["Summer MW"]) if "Summer MW" in raw.columns else pd.Series([pd.NA] * n)
    winter = to_numeric_mw(raw["Winter MW"]) if "Winter MW" in raw.columns else pd.Series([pd.NA] * n)
    out["summer_capacity_mw"] = summer.values
    out["winter_capacity_mw"] = winter.values
    # capacity_mw = max(summer, winter) — do NOT add
    out["capacity_mw"] = pd.concat([summer, winter], axis=1).max(axis=1, skipna=True).values

    flags = capacity_flags(out["capacity_mw"])
    for c in flags.columns:
        out[c] = flags[c].values

    fuel = raw["Fuel"] if "Fuel" in raw.columns else pd.Series([None] * n)
    tech = parse_technology_fields(fuel_raw=fuel)
    for c in tech.columns:
        out[c] = tech[c].values

    states = normalize_state(raw["State"] if "State" in raw.columns else pd.Series([None] * n))
    out["state"] = states["state"].values
    out["state_code"] = states["state_code"].values
    out["county_name"] = clean_text(raw["County"] if "County" in raw.columns else pd.Series([None] * n)).values
    out["county_name_clean"] = out["county_name"].values

    poi = normalize_poi(raw["POI Name"] if "POI Name" in raw.columns else pd.Series([None] * n))
    out["poi_name"] = clean_text(raw["POI Name"] if "POI Name" in raw.columns else pd.Series([None] * n)).values
    out["poi_name_clean"] = poi["poi_name_clean"].values
    out["poi_key"] = poi["poi_key"].values

    out["transmission_owner"] = clean_text(
        raw["Transmission Owner"] if "Transmission Owner" in raw.columns else pd.Series([None] * n)
    ).values
    out["transmission_owner_clean"] = out["transmission_owner"].values

    out["study_cycle"] = as_string_id(raw["Study Cycle"]) if "Study Cycle" in raw.columns else None
    out["study_group"] = as_string_id(raw["Study Group"]) if "Study Group" in raw.columns else None
    out["study_phase"] = clean_text(raw["Study Phase"]) if "Study Phase" in raw.columns else None
    out["service_type"] = clean_text(raw["Service Type"]) if "Service Type" in raw.columns else None
    out["post_gia_status"] = clean_text(raw["Post GIA Status"]) if "Post GIA Status" in raw.columns else None

    # Keep ERIS / NRIS separate
    for dest, src_col in [
        ("dp1_eris_mw", "Decision Point 1 ERIS MW"),
        ("dp1_nris_mw", "Decision Point 1 NRIS MW"),
        ("dp2_eris_mw", "Decision Point 2 ERIS MW"),
        ("dp2_nris_mw", "Decision Point 2 NRIS MW"),
    ]:
        if src_col in raw.columns:
            out[dest] = to_numeric_mw(raw[src_col]).values

    out["project_key"] = out["source_project_id"].map(lambda x: f"M::{x}" if x is not None else None)

    scores = [
        quality_score_row(st, cap, qd, sc, tech)
        for st, cap, qd, sc, tech in zip(
            out["status_clean"],
            out["capacity_mw"],
            out["queue_date"],
            out["state_code"],
            out["technology_primary"],
            strict=False,
        )
    ]
    out["quality_score"] = scores

    for col in raw.columns:
        out[f"raw_{col}"] = raw[col].map(lambda v: None if pd.isna(v) else str(v)).values

    return out


def standardize_all_miso() -> pd.DataFrame:
    ensure_layer_dirs()
    registry = load_registry_parquet()
    frames = []
    for _, source in registry[registry["source_name"] == "MISO"].iterrows():
        df = standardize_miso_source(source)
        out_path = SILVER_DIR / "projects" / f"{source['source_id']}.parquet"
        df.to_parquet(out_path, index=False)
        frames.append(df)
        print(f"MISO {source['source_id']}: {len(df)} rows -> {out_path.name}")
    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(all_df):
        all_df.to_parquet(SILVER_DIR / "projects" / "miso_all.parquet", index=False)
    return all_df


if __name__ == "__main__":
    standardize_all_miso()
