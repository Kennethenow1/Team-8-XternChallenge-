"""Standardize Berkeley / LBNL editions into the canonical Silver schema (MISO only)."""

from __future__ import annotations

from pathlib import Path

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


def _read_berkeley(path: Path, sheet_mode: str) -> pd.DataFrame:
    if sheet_mode == "berkeley_2020_split":
        frames = []
        for sheet in ("active", "withdrawn", "completed"):
            d = pd.read_excel(path, sheet_name=sheet)
            d["_sheet"] = sheet
            frames.append(d)
        df = pd.concat(frames, ignore_index=True, sort=False)
        # Harmonize column names across 2020 sheets
        rename = {
            "q_date_clean": "q_date",
            "proposed_on_date": "prop_date",
            "proposed_on_year": "prop_year",
            "ia_status_raw": "IA_status_raw",
            "ia_status_clean": "IA_status_clean",
            "ia_status": "IA_status_raw",
            "county": "county_1",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        return df
    if sheet_mode == "berkeley_data":
        return pd.read_excel(path, sheet_name="data")
    if sheet_mode == "berkeley_lbnl_complete":
        df = pd.read_excel(path, sheet_name="03. Complete Queue Data", header=1)
        rename = {
            "type_1": "type1",
            "type_2": "type2",
            "type_3": "type3",
            "mw_1": "mw1",
            "mw_2": "mw2",
            "mw_3": "mw3",
            "IA_phase_raw": "IA_status_raw",
            "IA_phase_clean": "IA_status_clean",
            "fips_code": "county_fips",
            "fips_codes": "county_fips",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        return df
    raise ValueError(sheet_mode)


def _county_from_row(df: pd.DataFrame) -> pd.Series:
    if "county_1" in df.columns:
        return _as_series(df["county_1"])
    if "county" in df.columns:
        return _as_series(df["county"])
    return pd.Series([None] * len(df))


def _as_series(obj: pd.Series | pd.DataFrame, n: int | None = None) -> pd.Series:
    """Excel concat can yield duplicate column names → DataFrame; take first column."""
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def _col_or_none(df: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in df.columns:
            return _as_series(df[name])
    return pd.Series([None] * len(df))


def standardize_berkeley_source(source: pd.Series) -> pd.DataFrame:
    path = BRONZE_DIR / source["bronze_subdir"] / source["source_file"]
    raw = _read_berkeley(path, source["sheet_mode"])

    # Filter to MISO
    col = source.get("region_filter_col") or "entity"
    val = source.get("region_filter_value") or "MISO"
    if col not in raw.columns and "region" in raw.columns:
        col = "region"
    raw = raw[raw[col].astype(str).str.upper() == str(val).upper()].copy()
    raw = raw.reset_index(drop=True)

    n = len(raw)
    out = pd.DataFrame({c: [None] * n for c in CANONICAL_COLUMNS})

    out["source_project_id"] = as_string_id(raw["q_id"])
    out["source_name"] = "Berkeley"
    out["source_id"] = source["source_id"]
    out["source_file"] = source["source_file"]
    out["observation_date"] = pd.to_datetime(source["data_as_of_date"])
    out["published_at"] = pd.to_datetime(source["published_at"])

    # Dates
    q_src = _col_or_none(raw, "q_date", "q_date_clean")
    wd_src = _col_or_none(raw, "wd_date")
    on_src = _col_or_none(raw, "on_date")
    prop_src = _col_or_none(raw, "prop_date", "proposed_on_date")

    for prefix, series in [
        ("queue_date", q_src),
        ("withdrawal_date", wd_src),
        ("operational_date", on_src),
        ("proposed_service_date", prop_src),
    ]:
        parsed = parse_date_series(series, prefix)
        for c in parsed.columns:
            out[c] = parsed[c].values

    # Status
    st = map_status(_col_or_none(raw, "q_status"), "berkeley")
    out["status_raw"] = st["status_raw"].values
    out["status_clean"] = st["status_clean"].values
    out["status"] = st["status"].values
    out["status_consistency_flag"] = status_consistency(
        out["status_clean"], out["withdrawal_date"], out["operational_date"]
    ).values

    # Capacity / technology
    type_clean = _col_or_none(raw, "type_clean") if "type_clean" in raw.columns else None
    type1 = _col_or_none(raw, "type1") if "type1" in raw.columns else None
    type2 = _col_or_none(raw, "type2") if "type2" in raw.columns else None
    type3 = _col_or_none(raw, "type3") if "type3" in raw.columns else None
    mw1 = to_numeric_mw(_col_or_none(raw, "mw1")) if "mw1" in raw.columns else None
    mw2 = to_numeric_mw(_col_or_none(raw, "mw2")) if "mw2" in raw.columns else None
    mw3 = to_numeric_mw(_col_or_none(raw, "mw3")) if "mw3" in raw.columns else None

    tech = parse_technology_fields(type_clean, type1, type2, type3, mw1, mw2, mw3)
    for c in tech.columns:
        out[c] = tech[c].values

    # Primary capacity = sum of component MWs when available, else mw1
    if mw1 is not None:
        comp = mw1.fillna(0)
        if mw2 is not None:
            comp = comp + mw2.fillna(0)
        if mw3 is not None:
            comp = comp + mw3.fillna(0)
        # If all components NaN, result 0 — restore to NA
        all_na = mw1.isna()
        if mw2 is not None:
            all_na = all_na & mw2.isna()
        if mw3 is not None:
            all_na = all_na & mw3.isna()
        capacity = comp.where(~all_na, other=pd.NA)
        # Prefer mw1 alone if only one component typically; still use sum for hybrids
        out["capacity_mw"] = capacity.values
    else:
        out["capacity_mw"] = None

    flags = capacity_flags(out["capacity_mw"])
    for c in flags.columns:
        out[c] = flags[c].values

    # Location
    county = _county_from_row(raw)
    out["county_name"] = clean_text(county).values
    out["county_name_clean"] = clean_text(county).values
    if "county_fips" in raw.columns:
        out["county_fips"] = as_string_id(_col_or_none(raw, "county_fips")).values
    states = normalize_state(_col_or_none(raw, "state"))
    out["state"] = states["state"].values
    out["state_code"] = states["state_code"].values

    poi_raw = _col_or_none(raw, "poi_name")
    poi = normalize_poi(poi_raw)
    out["poi_name"] = clean_text(poi_raw).values
    out["poi_name_clean"] = poi["poi_name_clean"].values
    out["poi_key"] = poi["poi_key"].values

    if "utility" in raw.columns:
        util = clean_text(_col_or_none(raw, "utility"))
        out["transmission_owner"] = util.values
        out["transmission_owner_clean"] = util.values

    if "service" in raw.columns:
        out["service_type"] = clean_text(_col_or_none(raw, "service")).values

    # Study / IA phase as study_phase when present
    for cand in ("IA_status_clean", "IA_status_raw", "IA_phase_clean"):
        if cand in raw.columns:
            out["study_phase"] = clean_text(_col_or_none(raw, cand)).values
            break

    # provisional project_key = Berkeley::{id} until crosswalk
    out["project_key"] = out["source_project_id"].map(
        lambda x: f"B::{x}" if x is not None else None
    )

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

    # Preserve uncertain / original columns as raw_* sidecars (stringified for parquet)
    seen = set()
    for col in raw.columns:
        if col in seen:
            continue
        seen.add(col)
        raw_name = f"raw_{col}"
        if raw_name not in out.columns:
            s = _as_series(raw[col])
            out[raw_name] = s.map(lambda v: None if pd.isna(v) else str(v)).values

    return out


def standardize_all_berkeley() -> pd.DataFrame:
    ensure_layer_dirs()
    registry = load_registry_parquet()
    frames = []
    for _, source in registry[registry["source_name"] == "Berkeley"].iterrows():
        df = standardize_berkeley_source(source)
        out_path = SILVER_DIR / "projects" / f"{source['source_id']}.parquet"
        df.to_parquet(out_path, index=False)
        frames.append(df)
        print(f"Berkeley {source['source_id']}: {len(df)} MISO rows -> {out_path.name}")
    if not frames:
        return pd.DataFrame()
    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_parquet(SILVER_DIR / "projects" / "berkeley_all.parquet", index=False)
    return all_df


if __name__ == "__main__":
    standardize_all_berkeley()
