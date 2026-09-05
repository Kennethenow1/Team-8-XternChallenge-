"""Populate high-value Silver enrichment tables from open data + queue history."""

from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    attach_metadata,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
    write_silver_table,
    SILVER_ENRICHMENT,
)
from src.enrichment.skeletons import write_empty_table


def _http_get(url: str, timeout: int = 180) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Team8-MISO-Enrichment/1.0; research)",
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        safe = re.sub(r"((?:api_)?key=)[^&\s]+", r"\1REDACTED", str(exc), flags=re.IGNORECASE)
        print(f"  download failed: {safe}")
        return None


# ---------------------------------------------------------------------------
# FRED rates / PPI
# ---------------------------------------------------------------------------

def populate_fred_into_market_zone_month() -> pd.DataFrame:
    """Download FRED DGS10 and a construction PPI series; store as national monthly series keyed zone=MISO."""
    ensure_enrichment_dirs()
    series = {
        "DGS10": "interest_rate_10y",
        "WPU10": "ppi_construction",
    }
    frames = []
    retrieved = utc_now_iso()
    for sid, col in series.items():
        # Try FRED CSV then fallback mirror
        urls = [
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}",
            f"https://fred.stlouisfed.org/data/{sid}.txt",
        ]
        raw = None
        for url in urls:
            raw = _http_get(url, timeout=240)
            if raw:
                break
        if raw is None:
            continue
        write_bronze_bytes("fred_rates", f"{sid}.csv", raw)
        text = raw.decode("utf-8", errors="replace")
        # Skip FRED .txt headers
        if "observation_date" in text.splitlines()[0] or text.startswith("DATE"):
            df = pd.read_csv(io.StringIO(text))
        else:
            lines = text.splitlines()
            start = 0
            for i, line in enumerate(lines):
                if line.startswith("DATE") or line.startswith("observation"):
                    start = i
                    break
            df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
        date_col = df.columns[0]
        val_col = df.columns[1]
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
        df = df.rename(columns={date_col: "effective_date", val_col: col})
        df = df.dropna(subset=["effective_date"])
        df["year_month"] = df["effective_date"].dt.to_period("M").astype(str)
        frames.append(df[["effective_date", "year_month", col]])

    if not frames:
        # Synthetic placeholder from public known approximate path — mark unavailable semantics via empty
        # Build minimal monthly frame from 2015-2026 with null rates so schema is populated
        print("FRED: downloads failed — writing schema-empty market_zone_month")
        return write_empty_table("market_zone_month")

    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=["year_month"], how="outer", suffixes=("", "_r"))
        if "effective_date_r" in out.columns:
            out["effective_date"] = out["effective_date"].fillna(out["effective_date_r"])
            out = out.drop(columns=["effective_date_r"])
    out["miso_zone"] = "MISO"
    out["geographic_key"] = "MISO"
    out["entity_key"] = out["year_month"]
    out["available_date"] = pd.to_datetime(out["effective_date"]) + pd.Timedelta(days=40)
    out["miso_mean_demand_mw"] = pd.NA
    out["miso_peak_demand_mw"] = pd.NA
    out["miso_demand_yoy_pct"] = pd.NA
    out["miso_generation_yoy_pct"] = pd.NA
    out["miso_net_interchange_mw"] = pd.NA
    out["demand_mw_mean"] = pd.NA
    out["demand_mw_peak"] = pd.NA
    out["net_interchange_mw"] = pd.NA
    out["local_demand_growth"] = pd.NA
    out["renewable_share"] = pd.NA
    out["local_congestion_mean"] = pd.NA
    out["local_congestion_volatility"] = pd.NA
    out = attach_metadata(
        out,
        source_name="FRED",
        source_url="https://fred.stlouisfed.org/",
        retrieved_at=retrieved,
        match_method="national_series",
        match_confidence=1.0,
        geographic_key_col="geographic_key",
        entity_key_col="entity_key",
    )
    write_silver_table("market_zone_month", out)
    print(f"market_zone_month (FRED) rows={len(out)}")
    return out


def populate_eia930_demand() -> pd.DataFrame:
    """Delegate to grid_pressure hourly EIA-930 path (requires EIA_API_KEY)."""
    from src.enrichment.grid_pressure import enrich_market_zone_demand_growth

    return enrich_market_zone_demand_growth()


# ---------------------------------------------------------------------------
# NOAA Storm Events (sample recent year)
# ---------------------------------------------------------------------------

def populate_weather_county_month() -> pd.DataFrame:
    ensure_enrichment_dirs()
    index_url = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
    raw = _http_get(index_url)
    retrieved = utc_now_iso()
    if not raw:
        print("NOAA Storm Events: index download failed")
        return write_empty_table("weather_county_month")
    write_bronze_bytes("noaa_storm_events", "index.html", raw, overwrite=True)
    text = raw.decode("utf-8", errors="ignore")
    # Prefer complete years 2020-2024 (not partial current year)
    wanted_years = ["2020", "2021", "2022", "2023", "2024"]
    files = []
    for year in wanted_years:
        full = re.findall(rf"StormEvents_details-ftp_v1\.0_d{year}_c\d+\.csv\.gz", text)
        if full:
            files.append(sorted(set(full))[-1])
    if not files:
        print("NOAA Storm Events: no 2020-2024 detail files found")
        return write_empty_table("weather_county_month")

    import gzip

    frames = []
    miso_states = {
        "IOWA", "ILLINOIS", "INDIANA", "MICHIGAN", "MINNESOTA", "MISSOURI",
        "NORTH DAKOTA", "SOUTH DAKOTA", "WISCONSIN", "ARKANSAS", "LOUISIANA",
        "MISSISSIPPI", "TEXAS", "MONTANA", "KENTUCKY",
    }
    for chosen in files:
        file_url = index_url + chosen
        blob = _http_get(file_url, timeout=180)
        if blob is None:
            continue
        write_bronze_bytes("noaa_storm_events", chosen, blob, overwrite=True)
        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as gz:
            df = pd.read_csv(gz, low_memory=False, dtype=str)
        if "STATE_FIPS" in df.columns and "CZ_FIPS" in df.columns and "CZ_TYPE" in df.columns:
            # County zones only (C) — avoid forecast-zone FIPS collision
            df = df[df["CZ_TYPE"].astype(str).str.upper().isin(["C", "COUNTY", "Z"]) | df["CZ_TYPE"].isna()]
            # Prefer county type C when present
            if (df["CZ_TYPE"].astype(str).str.upper() == "C").any():
                df = df[df["CZ_TYPE"].astype(str).str.upper() == "C"]
        if "STATE_FIPS" in df.columns and "CZ_FIPS" in df.columns:
            df["county_fips"] = df["STATE_FIPS"].str.zfill(2) + df["CZ_FIPS"].str.zfill(3)
        else:
            df["county_fips"] = None
        if "STATE" in df.columns:
            df = df[df["STATE"].str.upper().isin(miso_states)]
        df["BEGIN_DATE"] = pd.to_datetime(
            df.get("BEGIN_YEARMONTH", pd.Series([None] * len(df))).astype(str) + "01",
            errors="coerce",
        )

        def _parse_damage(x):
            if x is None or pd.isna(x) or str(x).strip() in {"", "0"}:
                return 0.0
            s = str(x).strip().upper().replace(",", "")
            mult = 1.0
            if s.endswith("K"):
                mult = 1e3
                s = s[:-1]
            elif s.endswith("M"):
                mult = 1e6
                s = s[:-1]
            try:
                return float(s) * mult
            except ValueError:
                return 0.0

        df["damage"] = df["DAMAGE_PROPERTY"].map(_parse_damage) if "DAMAGE_PROPERTY" in df.columns else 0.0
        df["year_month"] = df["BEGIN_DATE"].dt.to_period("M").astype(str)
        extreme = {"TORNADO", "FLOOD", "FLASH FLOOD", "HURRICANE", "WILDFIRE", "BLIZZARD", "ICE STORM"}
        df["is_extreme"] = (
            df["EVENT_TYPE"].str.upper().isin(extreme).astype(int) if "EVENT_TYPE" in df.columns else 0
        )
        frames.append(df)

    if not frames:
        return write_empty_table("weather_county_month")

    df = pd.concat(frames, ignore_index=True, sort=False)
    g = df.dropna(subset=["county_fips", "year_month"]).groupby(["county_fips", "year_month"], as_index=False).agg(
        storm_events=("EVENT_TYPE", "count") if "EVENT_TYPE" in df.columns else ("county_fips", "count"),
        storm_property_damage=("damage", "sum"),
        extreme_weather_days=("is_extreme", "sum"),
        effective_date=("BEGIN_DATE", "max"),
    )
    # Storm Events bulk files typically lag ~1-3 months; use +60d available_date
    g["available_date"] = g["effective_date"] + pd.Timedelta(days=60)
    g["temp_mean"] = pd.NA
    g["precip_mm"] = pd.NA
    g["snow_days"] = pd.NA
    g["geographic_key"] = g["county_fips"]
    g["entity_key"] = g["county_fips"].astype(str) + "|" + g["year_month"].astype(str)
    g = attach_metadata(
        g,
        source_name="NOAA Storm Events",
        source_url=index_url,
        retrieved_at=retrieved,
        match_method="county_fips",
        match_confidence=0.85,
        geographic_key_col="geographic_key",
        entity_key_col="entity_key",
    )
    write_silver_table("weather_county_month", g)
    cm = g[
        [
            c
            for c in [
                "county_fips",
                "year_month",
                "storm_events",
                "storm_property_damage",
                "extreme_weather_days",
                "effective_date",
                "available_date",
                "source_name",
                "source_url",
                "retrieved_at",
                "entity_key",
                "geographic_key",
                "match_method",
                "match_confidence",
            ]
            if c in g.columns
        ]
    ].copy()
    cm["construction_employment"] = pd.NA
    cm["construction_wage"] = pd.NA
    write_silver_table("county_month", cm)
    print(f"weather_county_month rows={len(g)} years={sorted(g['year_month'].str[:4].unique())}")
    return g


# ---------------------------------------------------------------------------
# FEMA NRI + Census county population (multi-year)
# ---------------------------------------------------------------------------

NRI_ARCGIS_QUERY = (
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
    "National_Risk_Index_Counties/FeatureServer/0/query"
)

POPEST_2023_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2023/"
    "counties/totals/co-est2023-alldata.csv"
)
POPEST_2020_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/"
    "counties/totals/co-est2020-alldata.csv"
)
PEP_CHARV_BASE = "https://api.census.gov/data/2023/pep/charv"
PEP_VINTAGE = 2023
PEP_YEARS = (2020, 2021, 2022, 2023)
# First public release approx for each July-1 estimate year (not the later vintage revision date)
PEP_AVAILABLE_BY_YEAR = {
    2020: pd.Timestamp("2021-05-01"),
    2021: pd.Timestamp("2022-03-01"),
    2022: pd.Timestamp("2023-03-01"),
    2023: pd.Timestamp("2024-03-14"),
}

EC_COAL_ZIP = (
    "https://edx.netl.doe.gov/storage/f/edx/2023/06/2023-06-15T18:32:19.438Z/"
    "de299df7-6cef-4d01-8819-13ce84da218e/ira_coal_closure_energy_comm_2023v2.zip"
)
EC_MSA_ZIP = (
    "https://edx.netl.doe.gov/storage/f/edx/2024/06/2024-06-07T01:36:36.743668/"
    "13454403-ef6b-479b-b720-d5e3eaefbb91/MSA_NMSA_EC_FFE_v2024_1.zip"
)


def _http_get_browser(url: str, timeout: int = 180) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        # Never echo API keys that may appear in query strings
        safe = re.sub(r"(key=)[^&]+", r"\1REDACTED", str(exc), flags=re.IGNORECASE)
        print(f"  download failed: {safe}")
        return None


def _fetch_pep_charv_year(year: int, api_key: str) -> pd.DataFrame | None:
    """Fetch county population for one YEAR from Census 2023 pep/charv API."""
    import urllib.parse

    params = {
        "get": "NAME,POP",
        "for": "county:*",
        "in": "state:*",
        "MONTH": "7",
        "YEAR": str(year),
        "UNIVERSE": "R",
        "key": api_key,
    }
    url = PEP_CHARV_BASE + "?" + urllib.parse.urlencode(params)
    raw = _http_get(url, timeout=180) or _http_get_browser(url, timeout=180)
    if raw is None:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        write_bronze_text("census_acs", f"pep_charv_{year}_parse_error.txt", str(exc), overwrite=True)
        return None
    if not isinstance(payload, list) or len(payload) < 2:
        write_bronze_text(
            "census_acs",
            f"pep_charv_{year}_empty.txt",
            "No rows returned from pep/charv.\n",
            overwrite=True,
        )
        return None
    header, *rows = payload
    # Scrub key before bronze (Census does not echo key in body, but keep raw without query)
    write_bronze_bytes(
        "census_acs",
        f"pep_charv_{year}.json",
        json.dumps([header] + rows).encode("utf-8"),
        overwrite=True,
    )
    df = pd.DataFrame(rows, columns=header)
    df["county_fips"] = df["state"].astype(str).str.zfill(2) + df["county"].astype(str).str.zfill(3)
    df["year"] = int(year)
    df["population"] = pd.to_numeric(df["POP"], errors="coerce")
    df["pep_vintage"] = PEP_VINTAGE
    df["effective_date"] = pd.Timestamp(f"{year}-07-01")
    df["available_date"] = PEP_AVAILABLE_BY_YEAR.get(year, pd.Timestamp(f"{year + 1}-03-01"))
    df["median_income"] = pd.NA
    df["rural_flag"] = (df["population"] < 50000).astype("Int64")
    df["fema_risk_score"] = pd.NA
    df["county_gdp"] = pd.NA
    df["county_gdp_growth"] = pd.NA
    df["energy_community_eligible"] = pd.NA
    return df[
        [
            "county_fips",
            "year",
            "population",
            "pep_vintage",
            "median_income",
            "rural_flag",
            "effective_date",
            "available_date",
            "fema_risk_score",
            "county_gdp",
            "county_gdp_growth",
            "energy_community_eligible",
        ]
    ].dropna(subset=["population"])


def _fetch_pep_charv_all(api_key: str) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    for year in PEP_YEARS:
        print(f"  Census pep/charv YEAR={year} ...")
        part = _fetch_pep_charv_year(year, api_key)
        if part is None or part.empty:
            print(f"  pep/charv YEAR={year} failed")
            continue
        print(f"  pep/charv YEAR={year} rows={len(part)}")
        frames.append(part)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _add_population_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add population_yoy_pct and population_change_since_2020 within each county."""
    if df.empty or "population" not in df.columns:
        return df
    out = df.copy()
    out["population"] = pd.to_numeric(out["population"], errors="coerce")
    out = out.sort_values(["county_fips", "year"])
    out["population_yoy_pct"] = out.groupby("county_fips")["population"].pct_change() * 100.0
    base = out.loc[out["year"] == 2020, ["county_fips", "population"]].rename(
        columns={"population": "_pop_2020"}
    )
    out = out.merge(base, on="county_fips", how="left")
    out["population_change_since_2020"] = out["population"] - out["_pop_2020"]
    out = out.drop(columns=["_pop_2020"])
    if "pep_vintage" not in out.columns:
        out["pep_vintage"] = pd.NA
    return out


def _fetch_fema_nri_counties() -> pd.DataFrame | None:
    """Pull county RISK_SCORE via ArcGIS FeatureServer (FEMA zip mirrors often 403)."""
    frames: list[pd.DataFrame] = []
    offset = 0
    page = 2000
    while True:
        url = (
            f"{NRI_ARCGIS_QUERY}?where=1%3D1"
            f"&outFields=STCOFIPS,RISK_SCORE,COUNTY,STATEABBRV"
            f"&returnGeometry=false&f=json&resultOffset={offset}&resultRecordCount={page}"
        )
        raw = _http_get_browser(url, timeout=120)
        if raw is None:
            break
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("fema_nri", "parse_error.txt", str(exc), overwrite=True)
            break
        feats = payload.get("features") or []
        if not feats:
            break
        rows = [f.get("attributes") or {} for f in feats]
        frames.append(pd.DataFrame(rows))
        if len(feats) < page:
            break
        offset += page
        if offset > 20000:
            break
    if frames:
        write_bronze_text(
            "fema_nri",
            "nri_arcgis_source.txt",
            f"{NRI_ARCGIS_QUERY}\nrows={sum(len(f) for f in frames)}\n",
            overwrite=True,
        )
    if not frames:
        # Fallback legacy zip URLs
        for u in [
            "https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/NRI_Table_Counties/NRI_Table_Counties.zip",
            "https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_counties.zip",
        ]:
            blob = _http_get_browser(u)
            if not blob:
                continue
            write_bronze_bytes("fema_nri", "nri_counties.zip", blob, overwrite=True)
            try:
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                    if not csvs:
                        continue
                    return pd.read_csv(zf.open(csvs[0]), low_memory=False, dtype=str)
            except Exception as exc:  # noqa: BLE001
                write_bronze_text("fema_nri", "parse_error.txt", str(exc), overwrite=True)
        write_bronze_text(
            "fema_nri",
            "DOWNLOAD_FAILED.txt",
            "ArcGIS NRI query and zip mirrors failed.\n",
            overwrite=True,
        )
        return None
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["STCOFIPS"])
    print(f"  FEMA NRI counties via ArcGIS: {len(out)}")
    return out


def _popest_long_from_csv(
    raw: bytes,
    years: list[int],
    *,
    available_by_year: dict[int, pd.Timestamp] | None = None,
    default_available: pd.Timestamp | None = None,
) -> pd.DataFrame:
    adf = pd.read_csv(io.BytesIO(raw), encoding="latin-1", dtype=str)
    if "SUMLEV" in adf.columns:
        adf = adf[adf["SUMLEV"] == "050"].copy()
    adf["county_fips"] = adf["STATE"].str.zfill(2) + adf["COUNTY"].str.zfill(3)
    rows: list[dict] = []
    for year in years:
        col = f"POPESTIMATE{year}"
        if col not in adf.columns:
            continue
        avail = None
        if available_by_year and year in available_by_year:
            avail = available_by_year[year]
        elif default_available is not None:
            avail = default_available
        else:
            # July 1 estimate typically published the following spring
            avail = pd.Timestamp(f"{year + 1}-03-01")
        for _, r in adf.iterrows():
            pop = pd.to_numeric(r[col], errors="coerce")
            if pd.isna(pop):
                continue
            rows.append(
                {
                    "county_fips": r["county_fips"],
                    "year": year,
                    "population": float(pop),
                    "median_income": pd.NA,
                    "rural_flag": int(float(pop) < 50000),
                    "effective_date": pd.Timestamp(f"{year}-07-01"),
                    "available_date": avail,
                    "fema_risk_score": pd.NA,
                    "county_gdp": pd.NA,
                    "county_gdp_growth": pd.NA,
                    "energy_community_eligible": pd.NA,
                }
            )
    return pd.DataFrame(rows)


def populate_county_year_fema_acs() -> pd.DataFrame:
    ensure_enrichment_dirs()
    retrieved = utc_now_iso()

    fema_df = _fetch_fema_nri_counties()
    fema_part = None
    if fema_df is not None and len(fema_df):
        fips_col = next(
            (c for c in fema_df.columns if str(c).upper() in {"STCOFIPS", "COUNTYFIPS", "FIPS"}),
            None,
        )
        risk_col = next(
            (c for c in fema_df.columns if "RISK_SCORE" in str(c).upper()),
            None,
        )
        if fips_col:
            fema_part = pd.DataFrame(
                {
                    "county_fips": fema_df[fips_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5),
                    "fema_risk_score": pd.to_numeric(fema_df[risk_col], errors="coerce") if risk_col else pd.NA,
                }
            ).drop_duplicates(subset=["county_fips"])

    # Prefer Census 2023 pep/charv API (requires CENSUS_API_KEY); fall back to popest CSV.
    import os

    pop_frames: list[pd.DataFrame] = []
    census_key = os.environ.get("CENSUS_API_KEY", "").strip()
    pep = _fetch_pep_charv_all(census_key) if census_key else None
    if pep is not None and len(pep):
        pop_frames.append(pep)
        print(f"  pep/charv 2020-2023 total rows={len(pep)} vintage={PEP_VINTAGE}")
    else:
        if not census_key:
            write_bronze_text(
                "census_acs",
                "NOTE_API_KEY.txt",
                "Set CENSUS_API_KEY in .env to use pep/charv API; falling back to popest CSV.\n",
                overwrite=True,
            )
        pop_raw = _http_get(POPEST_2023_URL, timeout=180) or _http_get_browser(POPEST_2023_URL)
        if pop_raw:
            write_bronze_bytes("census_acs", "co-est2023-alldata.csv", pop_raw, overwrite=True)
            try:
                part = _popest_long_from_csv(
                    pop_raw,
                    years=list(PEP_YEARS),
                    available_by_year=dict(PEP_AVAILABLE_BY_YEAR),
                )
                part["pep_vintage"] = PEP_VINTAGE
                pop_frames.append(part)
                print(f"  popest CSV 2020-2023 rows={len(part)} (API fallback)")
            except Exception as exc:  # noqa: BLE001
                write_bronze_text("census_acs", "parse_error.txt", str(exc), overwrite=True)
        else:
            write_bronze_text(
                "census_acs",
                "NOTE.txt",
                "pep/charv and co-est2023-alldata.csv both failed.\n",
                overwrite=True,
            )

    # 2019 from 2010–2020 vintage file (not in 2023 pep/charv YEAR loop above)
    pop20 = _http_get(POPEST_2020_URL, timeout=180) or _http_get_browser(POPEST_2020_URL)
    if pop20:
        write_bronze_bytes("census_acs", "co-est2020-alldata.csv", pop20, overwrite=True)
        try:
            part19 = _popest_long_from_csv(
                pop20,
                years=[2019],
                available_by_year={2019: pd.Timestamp("2020-03-26")},
            )
            part19["pep_vintage"] = 2020
            pop_frames.append(part19)
            print(f"  popest 2019 rows={len(part19)}")
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("census_acs", "parse_error_2020.txt", str(exc), overwrite=True)

    acs_part = pd.concat(pop_frames, ignore_index=True) if pop_frames else None
    if acs_part is not None and len(acs_part):
        acs_part = _add_population_derived(acs_part)

    if acs_part is not None and fema_part is not None:
        # Attach FEMA risk onto every population year row for the county (asof uses available_date)
        out = acs_part.merge(fema_part, on="county_fips", how="left", suffixes=("", "_fema"))
        if "fema_risk_score_fema" in out.columns:
            out["fema_risk_score"] = out["fema_risk_score"].fillna(out["fema_risk_score_fema"])
            out = out.drop(columns=["fema_risk_score_fema"])
        # Also keep FEMA-only counties for years without pop (rare)
        missing = fema_part[~fema_part["county_fips"].isin(out["county_fips"])].copy()
        if len(missing):
            missing["year"] = 2023
            missing["population"] = pd.NA
            missing["median_income"] = pd.NA
            missing["rural_flag"] = pd.NA
            missing["effective_date"] = pd.Timestamp("2023-01-01")
            missing["available_date"] = pd.Timestamp("2025-12-15")
            missing["county_gdp"] = pd.NA
            missing["county_gdp_growth"] = pd.NA
            missing["energy_community_eligible"] = pd.NA
            out = pd.concat([out, missing], ignore_index=True)
    elif acs_part is not None:
        out = acs_part
    elif fema_part is not None:
        out = fema_part.copy()
        out["year"] = 2023
        out["population"] = pd.NA
        out["median_income"] = pd.NA
        out["rural_flag"] = pd.NA
        out["effective_date"] = pd.Timestamp("2023-01-01")
        out["available_date"] = pd.Timestamp("2025-12-15")
        out["county_gdp"] = pd.NA
        out["county_gdp_growth"] = pd.NA
        out["energy_community_eligible"] = pd.NA
    else:
        out = None

    if out is None or out.empty:
        print("county_year: no FEMA/ACS data — empty")
        return write_empty_table("county_year")

    for c in (
        "county_gdp",
        "county_gdp_growth",
        "energy_community_eligible",
        "fema_risk_score",
        "median_income",
        "pep_vintage",
        "population_yoy_pct",
        "population_change_since_2020",
    ):
        if c not in out.columns:
            out[c] = pd.NA

    out["geographic_key"] = out["county_fips"]
    out["entity_key"] = out["county_fips"].astype(str) + "|" + out["year"].astype(str)
    out = attach_metadata(
        out,
        source_name="FEMA NRI / Census pep/charv 2023",
        source_url="https://www.fema.gov/about/openfema/data-sets/national-risk-index-data;https://api.census.gov/data/2023/pep/charv",
        retrieved_at=retrieved,
        match_method="county_fips",
        match_confidence=0.9,
        geographic_key_col="geographic_key",
        entity_key_col="entity_key",
    )
    write_silver_table("county_year", out)
    print(
        f"county_year rows={len(out)} years={sorted(out['year'].dropna().unique().tolist())} "
        f"pop_nonnull={float(out['population'].notna().mean()):.3f} "
        f"fema_nonnull={float(out['fema_risk_score'].notna().mean()):.3f}"
    )
    return out


# ---------------------------------------------------------------------------
# Energy communities (DOE/NETL EDX layers)
# ---------------------------------------------------------------------------

def populate_policy_energy_communities() -> pd.DataFrame:
    ensure_enrichment_dirs()
    retrieved = utc_now_iso()
    fips_set: set[str] = set()
    used_urls: list[str] = []

    # Coal-closure tracts → county FIPS
    coal_blob = _http_get_browser(EC_COAL_ZIP, timeout=300)
    if coal_blob:
        write_bronze_bytes("treasury_energy_communities", "ira_coal_closure_2023v2.zip", coal_blob, overwrite=True)
        try:
            with zipfile.ZipFile(io.BytesIO(coal_blob)) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    cdf = pd.read_csv(zf.open(csvs[0]), dtype=str)
                    col = next(
                        (c for c in cdf.columns if c.lower() in {"geoid_county_2020", "geoid_county", "county_fips"}),
                        None,
                    )
                    if col:
                        fips_set |= set(
                            cdf[col].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
                        )
                        used_urls.append(EC_COAL_ZIP)
                        print(f"  EC coal-closure counties={len(fips_set)}")
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("treasury_energy_communities", "coal_parse_error.txt", str(exc), overwrite=True)
    else:
        write_bronze_text(
            "treasury_energy_communities",
            "coal_download_failed.txt",
            f"{EC_COAL_ZIP}\n",
            overwrite=True,
        )

    # MSA/non-MSA FFE + unemployment energy communities (ec_qual_status == Yes)
    msa_blob = _http_get_browser(EC_MSA_ZIP, timeout=300)
    if msa_blob:
        write_bronze_bytes("treasury_energy_communities", "msa_nmsa_ec_ffe_v2024_1.zip", msa_blob, overwrite=True)
        try:
            with zipfile.ZipFile(io.BytesIO(msa_blob)) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv") and "energy" in n.lower()]
                if not csvs:
                    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    mdf = pd.read_csv(zf.open(csvs[0]), dtype=str)
                    fips_col = next(
                        (
                            c
                            for c in mdf.columns
                            if c.lower() in {"geoid_county_2020", "geoid_county", "county_fips"}
                        ),
                        None,
                    )
                    status_col = next((c for c in mdf.columns if c.lower() == "ec_qual_status"), None)
                    if fips_col:
                        sub = mdf
                        if status_col:
                            sub = mdf[mdf[status_col].astype(str).str.strip().str.lower().isin({"yes", "y", "1", "true"})]
                        before = len(fips_set)
                        fips_set |= set(
                            sub[fips_col].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
                        )
                        used_urls.append(EC_MSA_ZIP)
                        print(f"  EC MSA/non-MSA added={len(fips_set) - before} total={len(fips_set)}")
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("treasury_energy_communities", "msa_parse_error.txt", str(exc), overwrite=True)
    else:
        write_bronze_text(
            "treasury_energy_communities",
            "msa_download_failed.txt",
            f"{EC_MSA_ZIP}\n",
            overwrite=True,
        )

    if not fips_set:
        print("Energy communities: download failed — empty policy_state_date")
        return write_empty_table("policy_state_date")

    out = pd.DataFrame(
        {
            "county_fips": sorted(fips_set),
            "state_code": None,
            "policy_type": "energy_community_bonus",
            "energy_community_eligible": 1,
            "policy_id": "IRA_EC",
            "effective_date": pd.Timestamp("2023-01-01"),
            "available_date": pd.Timestamp("2023-06-15"),
        }
    )
    out["geographic_key"] = out["county_fips"]
    out["entity_key"] = out["county_fips"]
    out = attach_metadata(
        out,
        source_name="DOE/NETL Energy Communities (EDX)",
        source_url=";".join(used_urls) if used_urls else None,
        retrieved_at=retrieved,
        match_method="county_fips",
        match_confidence=0.95,
        geographic_key_col="geographic_key",
        entity_key_col="entity_key",
    )
    write_silver_table("policy_state_date", out)
    print(f"policy_state_date rows={len(out)}")
    return out


# ---------------------------------------------------------------------------
# Queue-derived study events + POI pressure
# ---------------------------------------------------------------------------

def populate_study_events_from_queue() -> pd.DataFrame:
    """Deprecated path — writes queue_study_status only (not historical study_events)."""
    from src.enrichment.study_tables import rename_queue_study_status

    rename_queue_study_status()
    path = SILVER_ENRICHMENT / "queue_study_status.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def populate_developer_quarter() -> pd.DataFrame:
    ensure_enrichment_dirs()
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    dev_path = SILVER_DIR / "crosswalks" / "developer_crosswalk.parquet"
    if not dev_path.exists():
        return write_empty_table("developer_quarter")
    dev = pd.read_parquet(dev_path)
    m = snaps.merge(dev[["project_key", "developer_id"]], on="project_key", how="left")
    m = m[m["developer_id"].notna()].copy()
    m["observation_date"] = pd.to_datetime(m["observation_date"])
    m["year_quarter"] = m["observation_date"].dt.to_period("Q").astype(str)
    m["capacity_mw"] = pd.to_numeric(m["capacity_mw"], errors="coerce")

    rows = []
    for (did, yq), g in m.groupby(["developer_id", "year_quarter"]):
        active = g[g["status_clean"] == "active"]
        # Prior history: all observations strictly before this quarter end
        q_end = pd.Period(yq).end_time
        hist = m[(m["developer_id"] == did) & (m["observation_date"] < q_end)]
        # Unique projects outcomes approximation from latest status in hist
        if len(hist):
            last = hist.sort_values("observation_date").groupby("project_key").tail(1)
            n = len(last)
            n_wd = int((last["status_clean"] == "withdrawn").sum())
            n_op = int((last["status_clean"].isin(["operational", "completed"])).sum())
            prior_wd = n_wd / n if n else None
            prior_comp = n_op / n if n else None
        else:
            prior_wd = None
            prior_comp = None

        rows.append(
            {
                "developer_id": did,
                "year_quarter": yq,
                "developer_active_project_count": int(active["project_key"].nunique()),
                "developer_total_active_mw": float(active["capacity_mw"].sum(skipna=True)),
                "developer_prior_completion_rate": prior_comp,
                "developer_prior_withdrawal_rate": prior_wd,
                "developer_financing_event_180d": pd.NA,  # SEC skeleton
                "developer_distress_event_180d": pd.NA,
                "effective_date": q_end.normalize(),
                "available_date": q_end.normalize(),
                "entity_key": did,
                "geographic_key": None,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return write_empty_table("developer_quarter")
    out = attach_metadata(
        out,
        source_name="Queue developer history",
        source_url=None,
        match_method="normalized_developer_name",
        match_confidence=0.8,
        entity_key_col="entity_key",
    )
    write_silver_table("developer_quarter", out)
    print(f"developer_quarter rows={len(out)}")
    return out


def populate_all(*, run_deferred_county_joins: bool = False) -> None:
    ensure_enrichment_dirs()
    print("=== Populate FRED ===")
    populate_fred_into_market_zone_month()
    print("=== Populate EIA-930 ===")
    populate_eia930_demand()
    print("=== Populate NOAA Storm Events ===")
    populate_weather_county_month()
    if run_deferred_county_joins:
        print("=== Populate FEMA/ACS county_year ===")
        populate_county_year_fema_acs()
        print("=== Populate Energy Communities ===")
        populate_policy_energy_communities()
    else:
        print(
            "=== Skip FEMA/ACS + Energy Communities "
            "(run_deferred_county_joins=False until FIPS coverage OK) ==="
        )
    print("=== Populate study_events from queue ===")
    populate_study_events_from_queue()
    print("=== Populate developer_quarter ===")
    populate_developer_quarter()


if __name__ == "__main__":
    populate_all()
