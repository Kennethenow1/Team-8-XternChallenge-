"""Geo and entity crosswalks for enrichment joins."""

from __future__ import annotations

import io
import re
import urllib.request
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    ensure_enrichment_dirs,
    write_bronze_bytes,
)

# Simplified MISO study-group → planning zone heuristic
_STUDY_GROUP_ZONE = {
    "WEST": "West",
    "EAST": "East",
    "EAST (ATC)": "East",
    "CENTRAL": "Central",
    "SOUTH": "South",
}

_FUZZY_SCORE_CUTOFF = 88.0
_GEO_COVERAGE_GATE = 0.90


def _norm_county(name: str | None) -> str | None:
    """Normalize county / parish / borough names for FIPS matching."""
    if name is None or pd.isna(name):
        return None
    s = str(name).upper().strip()
    s = re.sub(r"\bST\.?\b", "SAINT", s)
    s = re.sub(r"\bSTE\.?\b", "SAINTE", s)
    s = re.sub(
        r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA|CITY AND BOROUGH|MUNICIPIO|CITY|MUNICIPALITY)\b",
        " ",
        s,
    )
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _primary_county(name: str | None) -> tuple[str | None, int]:
    """Split multi-county strings; return (primary raw name, multi_county flag)."""
    if name is None or pd.isna(name):
        return None, 0
    parts = re.split(r"[,;/]| and ", str(name), flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        return None, 0
    return parts[0], int(len(parts) > 1)


def _norm_developer(name: str | None) -> str | None:
    if name is None or pd.isna(name):
        return None
    s = str(name).upper().strip()
    s = re.sub(r"\b(LLC|INC|CORP|CO|COMPANY|LP|LLP)\b", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def download_census_county_fips() -> pd.DataFrame:
    """National county FIPS from Census reference files (with centroids when present)."""
    ensure_enrichment_dirs()
    urls = [
        "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt",
        "https://www2.census.gov/geo/docs/reference/codes/files/national_county.txt",
    ]
    content = None
    used = None
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Team8-MISO-Enrichment/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                content = resp.read()
                used = u
                break
        except Exception:  # noqa: BLE001
            continue

    if content is None:
        raise RuntimeError("Could not download Census county FIPS reference file")

    write_bronze_bytes("census_county_fips", Path(used).name, content, overwrite=True)
    text = content.decode("latin-1", errors="replace")
    first = text.splitlines()[0]
    sep = "|" if "|" in first else ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
    rename = {}
    for c in df.columns:
        cu = c.upper()
        if cu in {"STATE", "STUSAB"}:
            rename[c] = "STATE"
        elif cu == "STATEFP":
            rename[c] = "STATEFP"
        elif cu == "COUNTYFP":
            rename[c] = "COUNTYFP"
        elif cu in {"COUNTYNAME", "COUNTY_NAME", "NAME"}:
            rename[c] = "COUNTYNAME"
        elif cu in {"INTPTLAT", "LAT"}:
            rename[c] = "INTPTLAT"
        elif cu in {"INTPTLON", "LON", "LONG"}:
            rename[c] = "INTPTLON"
    df = df.rename(columns=rename)
    if "STATEFP" in df.columns and "COUNTYFP" in df.columns:
        df["county_fips"] = df["STATEFP"].str.zfill(2) + df["COUNTYFP"].str.zfill(3)
    else:
        df["county_fips"] = None
    df["county_name_norm"] = df["COUNTYNAME"].map(_norm_county) if "COUNTYNAME" in df.columns else None
    df["state_code"] = df["STATE"] if "STATE" in df.columns else None
    if "INTPTLAT" in df.columns:
        df["latitude"] = pd.to_numeric(df["INTPTLAT"], errors="coerce")
    else:
        df["latitude"] = pd.NA
    if "INTPTLON" in df.columns:
        df["longitude"] = pd.to_numeric(df["INTPTLON"], errors="coerce")
    else:
        df["longitude"] = pd.NA
    return df


def _fuzzy_match_county(
    state: str,
    name_norm: str,
    by_state: dict[str, pd.DataFrame],
) -> tuple[str | None, float, str | None]:
    """Return (county_fips, match_score, matched_name_norm) within the same state only."""
    pool = by_state.get(state)
    if pool is None or pool.empty or not name_norm:
        return None, 0.0, None
    choices = pool["county_name_norm"].tolist()
    hit = process.extractOne(
        name_norm,
        choices,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=_FUZZY_SCORE_CUTOFF,
    )
    if hit is None:
        return None, 0.0, None
    matched_name, score, _idx = hit
    fips = pool.loc[pool["county_name_norm"] == matched_name, "county_fips"].iloc[0]
    return str(fips).zfill(5), float(score), matched_name


def build_geo_crosswalk(*, enforce_gate: bool = True) -> pd.DataFrame:
    """Build project→county_fips crosswalk. Joins counties via source_project_id."""
    ensure_enrichment_dirs()
    fips = download_census_county_fips()
    fips_lookup = (
        fips.dropna(subset=["county_name_norm", "state_code", "county_fips"])
        .drop_duplicates(["state_code", "county_name_norm"])
        .copy()
    )
    fips_lookup["county_fips"] = fips_lookup["county_fips"].astype(str).str.zfill(5)
    by_state = {st: g.reset_index(drop=True) for st, g in fips_lookup.groupby("state_code")}

    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    latest = snaps.sort_values("observation_date").groupby("project_key", as_index=False).tail(1)

    attr_frames = []
    for name in ("berkeley_all.parquet", "miso_all.parquet"):
        p = SILVER_DIR / "projects" / name
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        cols = [
            c
            for c in [
                "source_project_id",
                "county_name",
                "county_fips",
                "state_code",
                "poi_key",
                "study_group",
                "observation_date",
                "source_name",
            ]
            if c in df.columns
        ]
        attr_frames.append(df[cols])

    attrs = pd.concat(attr_frames, ignore_index=True, sort=False)
    sort_col = "observation_date" if "observation_date" in attrs.columns else "source_project_id"
    attrs["_has_county"] = attrs["county_name"].notna().astype(int) if "county_name" in attrs.columns else 0
    attrs = attrs.sort_values(["_has_county", sort_col], ascending=[False, True])
    attrs = attrs.drop_duplicates("source_project_id", keep="first")

    base = latest[
        ["project_key", "state_code", "poi_key", "county_fips", "source_project_id", "source_name"]
    ].copy()
    overlay_cols = [
        c
        for c in ["source_project_id", "county_name", "county_fips", "state_code", "poi_key", "study_group"]
        if c in attrs.columns
    ]
    ov = attrs[overlay_cols].rename(
        columns={
            "county_fips": "county_fips_src",
            "state_code": "state_code_src",
            "poi_key": "poi_key_src",
        }
    )
    base = base.merge(ov, on="source_project_id", how="left")
    base["state_code"] = base["state_code"].fillna(base.get("state_code_src"))
    base["poi_key"] = base["poi_key"].fillna(base.get("poi_key_src"))
    if "county_fips_src" in base.columns:
        base["county_fips"] = base["county_fips"].fillna(base["county_fips_src"])
    if "county_name" not in base.columns:
        base["county_name"] = None
    if "study_group" not in base.columns:
        base["study_group"] = None

    primary = base["county_name"].map(lambda x: _primary_county(x)[0])
    multi = base["county_name"].map(lambda x: _primary_county(x)[1])
    base["county_name_primary"] = primary
    base["multi_county"] = multi
    base["county_name_norm"] = primary.map(_norm_county)

    exact = fips_lookup.rename(
        columns={"county_fips": "county_fips_exact", "latitude": "lat_c", "longitude": "lon_c"}
    )
    merged = base.merge(
        exact[["state_code", "county_name_norm", "county_fips_exact", "lat_c", "lon_c"]],
        on=["state_code", "county_name_norm"],
        how="left",
    )

    match_methods, match_scores, fips_out, lats, lons, review_rows = [], [], [], [], [], []
    for _, r in merged.iterrows():
        existing = r.get("county_fips")
        if pd.notna(existing) and str(existing).strip() not in {"", "nan"}:
            fips_val = str(existing).replace(".0", "").zfill(5)
            match_methods.append("existing_fips")
            match_scores.append(100.0)
            fips_out.append(fips_val)
            lats.append(r.get("lat_c"))
            lons.append(r.get("lon_c"))
            continue

        if pd.notna(r.get("county_fips_exact")):
            match_methods.append("exact_state_county")
            match_scores.append(100.0)
            fips_out.append(str(r["county_fips_exact"]).zfill(5))
            lats.append(r.get("lat_c"))
            lons.append(r.get("lon_c"))
            continue

        st = r.get("state_code")
        nn = r.get("county_name_norm")
        if pd.notna(st) and pd.notna(nn):
            fips_f, score, matched = _fuzzy_match_county(str(st), str(nn), by_state)
            if fips_f:
                match_methods.append("fuzzy_same_state")
                match_scores.append(score)
                fips_out.append(fips_f)
                hit = fips_lookup[
                    (fips_lookup["state_code"] == st) & (fips_lookup["county_name_norm"] == matched)
                ]
                lats.append(hit["latitude"].iloc[0] if len(hit) else None)
                lons.append(hit["longitude"].iloc[0] if len(hit) else None)
                review_rows.append(
                    {
                        "project_key": r["project_key"],
                        "source_project_id": r["source_project_id"],
                        "state_code": st,
                        "county_name": r.get("county_name"),
                        "county_name_norm": nn,
                        "matched_county_norm": matched,
                        "county_fips": fips_f,
                        "match_method": "fuzzy_same_state",
                        "match_score": score,
                        "manual_review_status": "accepted_fuzzy",
                    }
                )
                continue

        match_methods.append("unmatched")
        match_scores.append(0.0)
        fips_out.append(None)
        lats.append(None)
        lons.append(None)
        review_rows.append(
            {
                "project_key": r["project_key"],
                "source_project_id": r["source_project_id"],
                "state_code": st,
                "county_name": r.get("county_name"),
                "county_name_norm": nn,
                "matched_county_norm": None,
                "county_fips": None,
                "match_method": "unmatched",
                "match_score": 0.0,
                "manual_review_status": "needs_review",
            }
        )

    merged["county_fips"] = fips_out
    merged["match_method"] = match_methods
    merged["match_score"] = match_scores
    merged["match_confidence"] = 0.0
    merged.loc[merged["match_method"].isin(["exact_state_county", "existing_fips"]), "match_confidence"] = 1.0
    merged.loc[merged["match_method"] == "fuzzy_same_state", "match_confidence"] = (
        merged.loc[merged["match_method"] == "fuzzy_same_state", "match_score"] / 100.0
    )
    merged["latitude"] = lats
    merged["longitude"] = lons
    merged["miso_zone"] = merged["study_group"].map(
        lambda x: _STUDY_GROUP_ZONE.get(str(x).upper().strip(), str(x) if pd.notna(x) else None)
    )
    merged["geographic_key"] = merged["county_fips"]
    merged["entity_key"] = merged["project_key"]

    state_to_fp = (
        fips.dropna(subset=["STATE", "STATEFP"])
        .drop_duplicates("STATE")
        .set_index("STATE")["STATEFP"]
        .to_dict()
        if "STATE" in fips.columns and "STATEFP" in fips.columns
        else {}
    )
    cross_state = 0
    for i, r in merged.iterrows():
        st, cf = r.get("state_code"), r.get("county_fips")
        if pd.isna(st) or pd.isna(cf):
            continue
        pref = state_to_fp.get(str(st))
        if pref and str(cf).zfill(5)[:2] != str(pref).zfill(2):
            cross_state += 1
            merged.at[i, "county_fips"] = None
            merged.at[i, "match_method"] = "rejected_cross_state"
            merged.at[i, "match_score"] = 0.0
            merged.at[i, "match_confidence"] = 0.0
            merged.at[i, "geographic_key"] = None

    out = merged[
        [
            "project_key",
            "source_project_id",
            "state_code",
            "county_name",
            "county_name_norm",
            "multi_county",
            "county_fips",
            "poi_key",
            "study_group",
            "miso_zone",
            "latitude",
            "longitude",
            "geographic_key",
            "entity_key",
            "match_method",
            "match_score",
            "match_confidence",
        ]
    ].drop_duplicates("project_key")

    path = SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet"
    out.to_parquet(path, index=False)
    out.to_csv(SILVER_DIR / "crosswalks" / "geo_crosswalk.csv", index=False)

    review = pd.DataFrame(review_rows)
    review.to_csv(ENRICHMENT_REPORTS / "geo_match_review.csv", index=False)
    review.to_csv(SILVER_DIR / "crosswalks" / "geo_match_review.csv", index=False)

    cov = float(out["county_fips"].notna().mean())
    print(
        f"geo_crosswalk rows={len(out)} fips_coverage={cov:.3f} "
        f"cross_state_rejected={cross_state} methods={out['match_method'].value_counts().to_dict()}"
    )
    if enforce_gate and cov < _GEO_COVERAGE_GATE:
        raise RuntimeError(f"Geo FIPS coverage gate failed: {cov:.3f} < {_GEO_COVERAGE_GATE}")
    return out


def build_developer_crosswalk() -> pd.DataFrame:
    ensure_enrichment_dirs()
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    id_map = (
        snaps.dropna(subset=["source_project_id"])
        .groupby("source_project_id", as_index=False)
        .agg(project_key=("project_key", "first"))
    )

    frames = []
    for pname in ("berkeley_all.parquet", "miso_all.parquet"):
        p = SILVER_DIR / "projects" / pname
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        sub = df[["source_project_id"]].copy()
        sub["developer_raw"] = df["raw_developer"] if "raw_developer" in df.columns else None
        util = None
        for c in ("transmission_owner_clean", "transmission_owner", "raw_utility", "raw_Transmission Owner"):
            if c in df.columns:
                util = df[c]
                break
        sub["utility_raw"] = util
        frames.append(sub)

    if not frames:
        out = pd.DataFrame(
            columns=[
                "project_key",
                "queue_project_id",
                "developer_id",
                "developer_raw",
                "match_method",
                "match_confidence",
            ]
        )
    else:
        all_d = pd.concat(frames, ignore_index=True)
        all_d["developer_norm"] = all_d["developer_raw"].map(_norm_developer)
        all_d["utility_norm"] = all_d["utility_raw"].map(_norm_developer)
        all_d["developer_id"] = all_d["developer_norm"].fillna(all_d["utility_norm"])
        all_d["match_method"] = all_d.apply(
            lambda r: "normalized_developer"
            if pd.notna(r["developer_norm"])
            else ("utility_proxy" if pd.notna(r["utility_norm"]) else "missing"),
            axis=1,
        )
        all_d["match_confidence"] = all_d["match_method"].map(
            {"normalized_developer": 0.9, "utility_proxy": 0.6, "missing": 0.0}
        )
        all_d = all_d.merge(id_map, on="source_project_id", how="left")
        all_d["project_key"] = all_d["project_key"].fillna(
            all_d["source_project_id"].map(lambda x: f"P::B::{x}" if pd.notna(x) else None)
        )
        all_d["queue_project_id"] = all_d["source_project_id"]
        all_d = all_d.sort_values("match_confidence", ascending=False).drop_duplicates("project_key")
        out = all_d[
            [
                "project_key",
                "queue_project_id",
                "developer_id",
                "developer_raw",
                "match_method",
                "match_confidence",
            ]
        ]

    path = SILVER_DIR / "crosswalks" / "developer_crosswalk.parquet"
    out.to_parquet(path, index=False)

    # Ambiguity review: utility_proxy + high-fanout developer_ids
    review_rows = out[out["match_method"] == "utility_proxy"].copy()
    counts = out.dropna(subset=["developer_id"]).groupby("developer_id").size()
    ambiguous_ids = set(counts[counts >= 50].index)
    amb = out[out["developer_id"].isin(ambiguous_ids)].copy()
    amb["notes"] = "high_fanout_developer_id"
    review_rows = pd.concat([review_rows.assign(notes="utility_proxy"), amb], ignore_index=True)
    review_rows = review_rows.drop_duplicates("project_key")
    review_rows.to_csv(ENRICHMENT_REPORTS / "developer_match_review.csv", index=False)
    review_rows.to_csv(SILVER_DIR / "crosswalks" / "developer_match_review.csv", index=False)

    print(
        f"developer_crosswalk rows={len(out)} "
        f"coverage={out['developer_id'].notna().mean():.3f} "
        f"review_rows={len(review_rows)}"
    )
    return out


def build_entity_crosswalk_eia() -> pd.DataFrame:
    """Scaffold or refresh EIA entity crosswalk shell (filled by ingest_eia860)."""
    ensure_enrichment_dirs()
    geo = pd.read_parquet(SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet")
    try:
        dev = pd.read_parquet(SILVER_DIR / "crosswalks" / "developer_crosswalk.parquet")
    except Exception:  # noqa: BLE001
        dev = pd.DataFrame(columns=["project_key", "developer_id"])

    base = geo.merge(dev[["project_key", "developer_id"]], on="project_key", how="left")
    out = pd.DataFrame(
        {
            "queue_project_id": base["source_project_id"],
            "project_key": base["project_key"],
            "eia_plant_id": None,
            "developer_id": base.get("developer_id"),
            "facility_name": None,
            "match_method": "unmatched_no_eia_source",
            "match_score": 0.0,
            "manual_review_status": "pending_eia_ingest",
        }
    )
    out.to_parquet(SILVER_DIR / "crosswalks" / "entity_crosswalk_eia.parquet", index=False)
    print(f"entity_crosswalk_eia rows={len(out)}")
    return out


def build_all_crosswalks(*, enforce_geo_gate: bool = True) -> dict[str, pd.DataFrame]:
    geo = build_geo_crosswalk(enforce_gate=enforce_geo_gate)
    dev = build_developer_crosswalk()
    eia = build_entity_crosswalk_eia()
    return {"geo": geo, "developer": dev, "eia": eia}


if __name__ == "__main__":
    build_all_crosswalks()
