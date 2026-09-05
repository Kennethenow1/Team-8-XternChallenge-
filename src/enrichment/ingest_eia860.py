"""Download and match EIA-860 / EIA-860M generator data."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import urllib.request

from src.common.paths import SILVER_DIR
from src.enrichment.build_crosswalks import _norm_county, _norm_developer
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
    write_silver_table,
)


def _http_get(url: str, timeout: int = 180) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Team8-MISO-Enrichment/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  EIA download failed {url}: {exc}")
        return None


def _norm_plant(name: str | None) -> str | None:
    if name is None or pd.isna(name):
        return None
    s = str(name).upper().strip()
    s = re.sub(r"\b(LLC|INC|CORP|LP|PLANT|FACILITY|SOLAR|WIND|FARM|ENERGY|PROJECT)\b", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def download_eia860() -> Path | None:
    ensure_enrichment_dirs()
    # Prefer archive/xls paths (current /xls/ often returns HTML)
    urls = [
        "https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602023.zip",
        "https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602022.zip",
        "https://www.eia.gov/electricity/data/eia860/archive/xls/eia8602024.zip",
        "https://www.eia.gov/electricity/data/eia860/xls/eia8602023.zip",
    ]
    for url in urls:
        blob = _http_get(url, timeout=300)
        if blob and len(blob) > 100_000 and blob[:2] == b"PK":
            dest = write_bronze_bytes("eia860", Path(url).name, blob, overwrite=True)
            print(f"Downloaded EIA-860 {dest.name} ({len(blob)} bytes)")
            return dest
        print(f"  skip non-zip response from {url} ({None if blob is None else len(blob)} bytes)")
    write_bronze_text("eia860", "DOWNLOAD_FAILED.txt", "All EIA-860 ZIP URLs failed\n", overwrite=True)
    return None


def download_eia860m() -> Path | None:
    ensure_enrichment_dirs()
    # Monthly generator inventory — try a few recent month patterns
    candidates = []
    # EIA page often hosts july_generatorYYYY.xlsx style names; try recent years
    for year in (2025, 2024, 2023):
        for month in (
            "december",
            "november",
            "october",
            "september",
            "august",
            "july",
            "june",
            "january",
        ):
            candidates.append(
                f"https://www.eia.gov/electricity/data/eia860m/xls/{month}_generator{year}.xlsx"
            )
    for url in candidates[:12]:
        blob = _http_get(url, timeout=180)
        if blob and len(blob) > 1000 and (blob[:2] == b"PK" or blob[:4] == b"\xd0\xcf\x11\xe0"):
            dest = write_bronze_bytes("eia860", Path(url).name, blob, overwrite=True)
            print(f"Downloaded EIA-860M {dest.name}")
            return dest
    write_bronze_text("eia860", "860M_DOWNLOAD_FAILED.txt", "EIA-860M workbook not retrieved\n", overwrite=True)
    return None


def _read_860_plants_generators(zip_path: Path) -> pd.DataFrame:
    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        plant_files = [n for n in names if re.search(r"plant", n, re.I) and n.lower().endswith((".xlsx", ".xls"))]
        gen_files = [n for n in names if re.search(r"generat", n, re.I) and n.lower().endswith((".xlsx", ".xls"))]
        plants = None
        gens = None
        if plant_files:
            with zf.open(plant_files[0]) as f:
                plants = pd.read_excel(f, sheet_name=0, skiprows=1)
        if gen_files:
            with zf.open(gen_files[0]) as f:
                gens = pd.read_excel(f, sheet_name=0, skiprows=1)
        if gens is None and not plant_files:
            # try any xlsx
            xlsx = [n for n in names if n.lower().endswith(".xlsx")]
            if xlsx:
                with zf.open(xlsx[0]) as f:
                    gens = pd.read_excel(f, sheet_name=0, skiprows=1)

    if gens is None:
        return pd.DataFrame()

    # Normalize columns
    colmap = {c: str(c).strip() for c in gens.columns}
    gens = gens.rename(columns=colmap)

    def pick(*cands):
        for c in gens.columns:
            cl = str(c).lower().replace("\n", " ")
            for cand in cands:
                if cand in cl:
                    return c
        return None

    plant_id = pick("plant code", "plant id")
    plant_name = pick("plant name")
    state = pick("state")
    county = pick("county")
    tech = pick("technology", "prime mover")
    status = pick("status")
    nameplate = pick("nameplate capacity", "nameplate")
    op_year = pick("operating year", "operating year")
    planned = pick("planned operation year", "planned operating year")

    out = pd.DataFrame()
    out["eia_plant_id"] = gens[plant_id].astype(str) if plant_id else None
    out["facility_name"] = gens[plant_name] if plant_name else None
    out["state_code"] = gens[state].astype(str).str.upper().str.strip() if state else None
    out["county_name"] = gens[county] if county else None
    out["technology"] = gens[tech] if tech else None
    out["status"] = gens[status] if status else None
    out["capacity_mw"] = pd.to_numeric(gens[nameplate], errors="coerce") if nameplate else pd.NA
    out["operating_year"] = pd.to_numeric(gens[op_year], errors="coerce") if op_year else pd.NA
    out["proposed_year"] = pd.to_numeric(gens[planned], errors="coerce") if planned else pd.NA
    out["county_name_norm"] = out["county_name"].map(_norm_county)
    out["facility_name_norm"] = out["facility_name"].map(_norm_plant)

    if plants is not None and plant_id:
        pcols = {c: str(c).strip() for c in plants.columns}
        plants = plants.rename(columns=pcols)
        pid = next((c for c in plants.columns if "plant code" in str(c).lower() or "plant id" in str(c).lower()), None)
        util = next((c for c in plants.columns if "utility" in str(c).lower() and "name" in str(c).lower()), None)
        if pid and util:
            pu = plants[[pid, util]].copy()
            pu.columns = ["eia_plant_id", "utility_name"]
            pu["eia_plant_id"] = pu["eia_plant_id"].astype(str)
            out = out.merge(pu.drop_duplicates("eia_plant_id"), on="eia_plant_id", how="left")
        else:
            out["utility_name"] = None
    else:
        out["utility_name"] = None

    # Filter to MISO-ish states
    miso_states = {
        "IA", "IL", "IN", "MI", "MN", "MO", "ND", "SD", "WI", "AR", "LA", "MS", "TX", "MT", "KY", "MANITOBA"
    }
    out = out[out["state_code"].isin(miso_states) | out["state_code"].isna()].copy()
    return out.reset_index(drop=True)


def build_generator_status_events(eia: pd.DataFrame, vintage_year: int = 2023) -> pd.DataFrame:
    if eia.empty:
        from src.enrichment.skeletons import write_empty_table

        return write_empty_table("generator_status_events")

    retrieved = utc_now_iso()
    # File vintage available ~ mid following year for annual 860
    available = pd.Timestamp(f"{vintage_year + 1}-10-01")
    effective = pd.Timestamp(f"{vintage_year}-12-31")

    rows = []
    for _, r in eia.iterrows():
        rows.append(
            {
                "eia_plant_id": r.get("eia_plant_id"),
                "project_key": None,
                "status": r.get("status"),
                "operating_date": pd.Timestamp(int(r["operating_year"]), 1, 1)
                if pd.notna(r.get("operating_year"))
                else pd.NaT,
                "capacity_mw": r.get("capacity_mw"),
                "technology": r.get("technology"),
                "event_type": "eia860_annual_inventory",
                "facility_name": r.get("facility_name"),
                "state_code": r.get("state_code"),
                "county_name": r.get("county_name"),
                "effective_date": effective,
                "available_date": available,
                "entity_key": r.get("eia_plant_id"),
                "geographic_key": r.get("state_code"),
            }
        )
    out = pd.DataFrame(rows)
    out = attach_metadata(
        out,
        source_name="EIA-860",
        source_url="https://www.eia.gov/electricity/data/eia860/",
        retrieved_at=retrieved,
        match_method="eia_inventory",
        match_confidence=1.0,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    write_silver_table("generator_status_events", out)
    # Also write dedicated month/annual table
    out.to_parquet(SILVER_ENRICHMENT / "eia_generator_month.parquet", index=False)
    print(f"generator_status_events rows={len(out)}")
    return out


def match_eia_to_queue(eia: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exact auto-accept on state + normalized facility name; fuzzy → review only."""
    geo = pd.read_parquet(SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet")
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    latest = snaps.sort_values("observation_date").groupby("project_key", as_index=False).tail(1)
    # Facility / project names from silver projects
    names = []
    for pname in ("berkeley_all.parquet", "miso_all.parquet"):
        p = SILVER_DIR / "projects" / pname
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        name_col = next(
            (
                c
                for c in df.columns
                if c
                in {
                    "raw_project_name",
                    "raw_Generating Facility",
                    "poi_name",
                    "raw_poi_name",
                }
                or c.lower() in {"project_name", "facility_name"}
            ),
            None,
        )
        # Prefer project_name over generating facility (often just "Photovoltaic")
        for preferred in ("raw_project_name", "project_name", "poi_name", "raw_poi_name"):
            if preferred in df.columns and df[preferred].notna().any():
                name_col = preferred
                break
        if name_col is None:
            continue
        sub = df[["source_project_id"]].copy()
        sub["facility_name"] = df[name_col]
        # Skip non-informative tech-only labels
        bad = {"photovoltaic", "solar", "wind", "battery", "storage", "gas", "hybrid"}
        sub.loc[sub["facility_name"].astype(str).str.strip().str.lower().isin(bad), "facility_name"] = pd.NA
        if "capacity_mw" in df.columns:
            sub["capacity_mw"] = df["capacity_mw"]
        if "technology_primary" in df.columns:
            sub["technology_primary"] = df["technology_primary"]
        if "state_code" in df.columns:
            sub["state_code"] = df["state_code"]
        names.append(sub)
    if not names:
        queue = latest.merge(geo[["project_key", "state_code", "county_fips"]], on="project_key", how="left")
        queue["facility_name"] = None
        queue["facility_name_norm"] = None
    else:
        qn = pd.concat(names, ignore_index=True).drop_duplicates("source_project_id")
        qn["facility_name_norm"] = qn["facility_name"].map(_norm_plant)
        queue = latest.merge(qn, on="source_project_id", how="left", suffixes=("", "_n"))
        if "state_code_n" in queue.columns:
            queue["state_code"] = queue["state_code"].fillna(queue["state_code_n"])
        if "capacity_mw_n" in queue.columns:
            queue["capacity_mw"] = queue.get("capacity_mw").fillna(queue["capacity_mw_n"]) if "capacity_mw" in queue.columns else queue["capacity_mw_n"]

    eia = eia.copy()
    eia["facility_name_norm"] = eia["facility_name"].map(_norm_plant)

    accepted = []
    review = []
    eia_by_key = {}
    for _, r in eia.dropna(subset=["facility_name_norm", "state_code"]).iterrows():
        key = (str(r["state_code"]).upper(), str(r["facility_name_norm"]))
        eia_by_key.setdefault(key, []).append(r)

    for _, q in queue.iterrows():
        st = q.get("state_code")
        nn = q.get("facility_name_norm")
        if pd.isna(st) or pd.isna(nn) or not nn:
            accepted.append(
                {
                    "queue_project_id": q.get("source_project_id"),
                    "project_key": q.get("project_key"),
                    "eia_plant_id": None,
                    "developer_id": None,
                    "facility_name": q.get("facility_name"),
                    "match_method": "unmatched_missing_name",
                    "match_score": 0.0,
                    "manual_review_status": "unmatched",
                }
            )
            continue
        key = (str(st).upper(), str(nn))
        cands = eia_by_key.get(key, [])
        if len(cands) == 1:
            c = cands[0]
            # validate capacity if both present
            score = 100.0
            ok = True
            qc = pd.to_numeric(q.get("capacity_mw"), errors="coerce")
            ec = pd.to_numeric(c.get("capacity_mw"), errors="coerce")
            if pd.notna(qc) and pd.notna(ec) and qc > 0:
                if abs(qc - ec) > max(10.0, 0.2 * qc):
                    ok = False
                    score = 70.0
            if ok:
                accepted.append(
                    {
                        "queue_project_id": q.get("source_project_id"),
                        "project_key": q.get("project_key"),
                        "eia_plant_id": c.get("eia_plant_id"),
                        "developer_id": _norm_developer(c.get("utility_name")),
                        "facility_name": c.get("facility_name"),
                        "match_method": "exact_state_facility_name",
                        "match_score": score,
                        "manual_review_status": "accepted",
                    }
                )
            else:
                review.append(
                    {
                        "queue_project_id": q.get("source_project_id"),
                        "candidate_eia_plant_id": c.get("eia_plant_id"),
                        "facility_name": c.get("facility_name"),
                        "match_score": score,
                        "match_method": "exact_name_capacity_conflict",
                        "manual_review_status": "needs_review",
                        "notes": f"queue_mw={qc} eia_mw={ec}",
                    }
                )
                accepted.append(
                    {
                        "queue_project_id": q.get("source_project_id"),
                        "project_key": q.get("project_key"),
                        "eia_plant_id": None,
                        "developer_id": None,
                        "facility_name": q.get("facility_name"),
                        "match_method": "held_for_review",
                        "match_score": score,
                        "manual_review_status": "needs_review",
                    }
                )
        elif len(cands) > 1:
            for c in cands:
                review.append(
                    {
                        "queue_project_id": q.get("source_project_id"),
                        "candidate_eia_plant_id": c.get("eia_plant_id"),
                        "facility_name": c.get("facility_name"),
                        "match_score": 90.0,
                        "match_method": "exact_name_ambiguous",
                        "manual_review_status": "needs_review",
                        "notes": "multiple EIA plants same state+name",
                    }
                )
            accepted.append(
                {
                    "queue_project_id": q.get("source_project_id"),
                    "project_key": q.get("project_key"),
                    "eia_plant_id": None,
                    "developer_id": None,
                    "facility_name": q.get("facility_name"),
                    "match_method": "ambiguous",
                    "match_score": 0.0,
                    "manual_review_status": "needs_review",
                }
            )
        else:
            accepted.append(
                {
                    "queue_project_id": q.get("source_project_id"),
                    "project_key": q.get("project_key"),
                    "eia_plant_id": None,
                    "developer_id": None,
                    "facility_name": q.get("facility_name"),
                    "match_method": "unmatched",
                    "match_score": 0.0,
                    "manual_review_status": "unmatched",
                }
            )

    cross = pd.DataFrame(accepted).drop_duplicates("project_key")
    rev = pd.DataFrame(review)
    cross.to_parquet(SILVER_DIR / "crosswalks" / "entity_crosswalk_eia.parquet", index=False)
    cross.to_csv(SILVER_DIR / "crosswalks" / "eia_project_crosswalk.csv", index=False)
    rev.to_csv(ENRICHMENT_REPORTS / "eia_match_review.csv", index=False)
    rev.to_csv(SILVER_DIR / "crosswalks" / "eia_match_review.csv", index=False)
    n_acc = int((cross["manual_review_status"] == "accepted").sum())
    print(f"EIA crosswalk accepted={n_acc} review={len(rev)} total={len(cross)}")
    return cross, rev


def populate_eia860() -> dict:
    ensure_enrichment_dirs()
    zpath = download_eia860()
    download_eia860m()  # best-effort
    if zpath is None:
        from src.enrichment.skeletons import write_empty_table

        write_empty_table("generator_status_events")
        return {"generators": 0, "accepted": 0}
    # infer vintage from filename
    m = re.search(r"(\d{4})", zpath.name)
    vintage = int(m.group(1)) if m else 2023
    eia = _read_860_plants_generators(zpath)
    print(f"EIA generators parsed (MISO states filter): {len(eia)}")
    build_generator_status_events(eia, vintage_year=vintage)
    cross, rev = match_eia_to_queue(eia)
    return {
        "generators": len(eia),
        "accepted": int((cross["manual_review_status"] == "accepted").sum()),
        "review": len(rev),
    }


if __name__ == "__main__":
    print(populate_eia860())
