"""Grid-pressure enrichment: EIA-930 hourly MISO demand/generation, HIFLD/MTEP context."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    SILVER_ENRICHMENT,
    attach_metadata,
    ensure_enrichment_dirs,
    write_bronze_bytes,
    write_bronze_text,
    write_silver_table,
)
from src.enrichment.skeletons import write_empty_table

EIA_REGION_DATA_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
EIA_PAGE_LENGTH = 5000
EIA_START = "2020-01-01"
# D=demand, NG=net generation, TI=total interchange
EIA_TYPES = ("D", "NG", "TI")

_MISO_FEATURE_COLS = (
    "miso_mean_demand_mw",
    "miso_peak_demand_mw",
    "miso_demand_yoy_pct",
    "miso_generation_yoy_pct",
    "miso_net_interchange_mw",
)


def _redact_api_key(url: str) -> str:
    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url, flags=re.IGNORECASE)


def _scrub_eia_payload_bytes(raw: bytes) -> bytes:
    """Remove api_key from EIA JSON echo of request.params before bronze write."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return raw
    params = payload.get("request", {}).get("params")
    if isinstance(params, dict) and "api_key" in params:
        params["api_key"] = "REDACTED"
        return json.dumps(payload).encode("utf-8")
    return raw


def _http_get(url: str, timeout: int = 120) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Team8-MISO-Enrichment/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  grid download failed: {_redact_api_key(str(exc))}")
        return None


def _prior_year_month(ym: str) -> str | None:
    try:
        y, mo = str(ym).split("-")
        return f"{int(y) - 1}-{mo}"
    except Exception:  # noqa: BLE001
        return None


def _yoy_pct(series_by_ym: dict[str, float], ym: str, val: float) -> float | object:
    p = series_by_ym.get(_prior_year_month(ym) or "")
    if p is None or pd.isna(val) or pd.isna(p) or p == 0:
        return pd.NA
    return float((val - p) / p * 100.0)


def _fetch_eia_type_series(api_key: str, type_code: str) -> pd.DataFrame:
    """Paginate hourly EIA region-data for one type facet; return period/value frame."""
    rows: list[dict] = []
    offset = 0
    page = 0
    while True:
        params = [
            ("api_key", api_key),
            ("frequency", "hourly"),
            ("data[0]", "value"),
            ("facets[respondent][]", "MISO"),
            ("facets[type][]", type_code),
            ("start", EIA_START),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("offset", str(offset)),
            ("length", str(EIA_PAGE_LENGTH)),
        ]
        url = EIA_REGION_DATA_URL + "?" + urllib.parse.urlencode(params)
        raw = _http_get(url, timeout=180)
        if raw is None:
            break
        safe_raw = _scrub_eia_payload_bytes(raw)
        write_bronze_bytes(
            "eia930",
            f"region_data_{type_code}_offset_{offset:06d}.json",
            safe_raw,
            overwrite=True,
        )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("eia930", f"parse_error_{type_code}.txt", str(exc), overwrite=True)
            break
        batch = payload.get("response", {}).get("data", []) or []
        if not batch:
            break
        rows.extend(batch)
        page += 1
        print(f"  EIA type={type_code} page={page} rows={len(batch)} total={len(rows)}")
        if len(batch) < EIA_PAGE_LENGTH:
            break
        offset += EIA_PAGE_LENGTH

    if not rows:
        return pd.DataFrame(columns=["period", "value", "type"])
    edf = pd.DataFrame(rows)
    edf["period"] = pd.to_datetime(edf["period"], errors="coerce")
    edf["value"] = pd.to_numeric(edf["value"], errors="coerce")
    edf["type"] = type_code
    return edf.dropna(subset=["period"])


def fetch_eia930_hourly_miso(api_key: str) -> pd.DataFrame:
    """Fetch D / NG / TI hourly series and return concatenated frame."""
    frames = []
    for type_code in EIA_TYPES:
        part = _fetch_eia_type_series(api_key, type_code)
        if len(part):
            frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["period", "value", "type", "year_month"])
    edf = pd.concat(frames, ignore_index=True)
    edf["year_month"] = edf["period"].dt.to_period("M").astype(str)
    return edf


def aggregate_miso_monthly(hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate hourly EIA series to monthly MISO-wide features.

    Values are balancing-authority-wide: every project in a month gets the same
    MISO demand/generation/interchange context.
    """
    if hourly.empty:
        return pd.DataFrame(
            columns=[
                "year_month",
                "effective_date",
                "available_date",
                *_MISO_FEATURE_COLS,
            ]
        )

    demand = hourly.loc[hourly["type"] == "D"].copy()
    gen = hourly.loc[hourly["type"] == "NG"].copy()
    ti = hourly.loc[hourly["type"] == "TI"].copy()

    monthly = None
    if len(demand):
        monthly = demand.groupby("year_month", as_index=False).agg(
            miso_mean_demand_mw=("value", "mean"),
            miso_peak_demand_mw=("value", "max"),
            effective_date=("period", "max"),
        )
    else:
        monthly = pd.DataFrame(columns=["year_month", "miso_mean_demand_mw", "miso_peak_demand_mw", "effective_date"])

    if len(gen):
        g = gen.groupby("year_month", as_index=False).agg(gen_mean=("value", "mean"), gen_max_period=("period", "max"))
        monthly = monthly.merge(g[["year_month", "gen_mean", "gen_max_period"]], on="year_month", how="outer")
        if "effective_date" in monthly.columns:
            monthly["effective_date"] = monthly["effective_date"].fillna(monthly["gen_max_period"])
        else:
            monthly["effective_date"] = monthly["gen_max_period"]
    else:
        monthly["gen_mean"] = pd.NA

    if len(ti):
        t = ti.groupby("year_month", as_index=False).agg(
            miso_net_interchange_mw=("value", "mean"),
            ti_max_period=("period", "max"),
        )
        monthly = monthly.merge(t[["year_month", "miso_net_interchange_mw", "ti_max_period"]], on="year_month", how="outer")
        monthly["effective_date"] = monthly.get("effective_date", pd.Series(dtype="datetime64[ns]"))
        monthly["effective_date"] = monthly["effective_date"].fillna(monthly["ti_max_period"])
    else:
        monthly["miso_net_interchange_mw"] = pd.NA

    monthly = monthly.sort_values("year_month").copy()
    monthly["effective_date"] = pd.to_datetime(monthly["effective_date"], errors="coerce")
    monthly["available_date"] = monthly["effective_date"] + pd.Timedelta(days=5)

    demand_map = {
        str(ym): float(v)
        for ym, v in zip(monthly["year_month"], monthly.get("miso_mean_demand_mw", pd.Series(dtype=float)), strict=False)
        if pd.notna(v)
    }
    gen_map = {
        str(ym): float(v)
        for ym, v in zip(monthly["year_month"], monthly.get("gen_mean", pd.Series(dtype=float)), strict=False)
        if pd.notna(v)
    }

    monthly["miso_demand_yoy_pct"] = [
        _yoy_pct(demand_map, str(ym), float(v) if pd.notna(v) else float("nan"))
        for ym, v in zip(monthly["year_month"], monthly.get("miso_mean_demand_mw", pd.Series(dtype=float)), strict=False)
    ]
    monthly["miso_generation_yoy_pct"] = [
        _yoy_pct(gen_map, str(ym), float(v) if pd.notna(v) else float("nan"))
        for ym, v in zip(monthly["year_month"], monthly.get("gen_mean", pd.Series(dtype=float)), strict=False)
    ]

    keep = [
        "year_month",
        "effective_date",
        "available_date",
        "miso_mean_demand_mw",
        "miso_peak_demand_mw",
        "miso_demand_yoy_pct",
        "miso_generation_yoy_pct",
        "miso_net_interchange_mw",
    ]
    for c in keep:
        if c not in monthly.columns:
            monthly[c] = pd.NA
    return monthly[keep]


def enrich_market_zone_demand_growth() -> pd.DataFrame:
    """Load EIA-930 hourly via API key; write MISO-wide monthly miso_* features onto market_zone_month."""
    ensure_enrichment_dirs()
    path = SILVER_ENRICHMENT / "market_zone_month.parquet"
    if path.exists():
        m = pd.read_parquet(path)
    else:
        m = write_empty_table("market_zone_month")

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        write_bronze_text(
            "eia930",
            "NOTE_API_KEY.txt",
            "Set EIA_API_KEY in .env (never commit) to populate MISO demand from EIA-930 API.\n",
            overwrite=True,
        )
        for c in _MISO_FEATURE_COLS:
            if c not in m.columns:
                m[c] = pd.NA
        # legacy aliases
        m["demand_mw_mean"] = m.get("miso_mean_demand_mw", pd.NA)
        m["demand_mw_peak"] = m.get("miso_peak_demand_mw", pd.NA)
        m["local_demand_growth"] = m.get("miso_demand_yoy_pct", pd.NA)
        m["net_interchange_mw"] = m.get("miso_net_interchange_mw", pd.NA)
    else:
        print("Fetching EIA-930 hourly region-data (MISO D/NG/TI from 2020-01-01)...")
        hourly = fetch_eia930_hourly_miso(api_key)
        monthly = aggregate_miso_monthly(hourly)
        if monthly.empty:
            write_bronze_text(
                "eia930",
                "DOWNLOAD_FAILED.txt",
                "EIA region-data returned no rows for MISO hourly D/NG/TI.\n",
                overwrite=True,
            )
        else:
            # Clear stale missing-key note once data lands
            from src.enrichment.registry import BRONZE_ENRICHMENT

            note = BRONZE_ENRICHMENT / "eia930" / "NOTE_API_KEY.txt"
            if note.exists():
                note.unlink()
            drop_cols = [
                *_MISO_FEATURE_COLS,
                "demand_mw_mean",
                "demand_mw_peak",
                "local_demand_growth",
                "net_interchange_mw",
                "eia_effective_date",
                "eia_available_date",
            ]
            if "year_month" in m.columns and len(m):
                m = m.drop(columns=[c for c in drop_cols if c in m.columns], errors="ignore")
                feat = monthly.copy()
                feat = feat.rename(
                    columns={
                        "effective_date": "eia_effective_date",
                        "available_date": "eia_available_date",
                    }
                )
                m = m.merge(feat, on="year_month", how="left")
                # Prefer EIA available_date when present for demand months
                if "available_date" in m.columns and "eia_available_date" in m.columns:
                    m["available_date"] = pd.to_datetime(m["available_date"], errors="coerce")
                    eia_av = pd.to_datetime(m["eia_available_date"], errors="coerce")
                    # keep FRED lag for rate rows; for months with EIA, tighten available_date to EIA lag
                    m.loc[eia_av.notna(), "available_date"] = eia_av[eia_av.notna()]
                m = m.drop(columns=["eia_effective_date", "eia_available_date"], errors="ignore")
            else:
                m = monthly.copy()
                m["miso_zone"] = "MISO"
                m["geographic_key"] = "MISO"
                m["entity_key"] = m["year_month"]

            # Legacy aliases for older consumers
            m["demand_mw_mean"] = m["miso_mean_demand_mw"]
            m["demand_mw_peak"] = m["miso_peak_demand_mw"]
            m["local_demand_growth"] = m["miso_demand_yoy_pct"]
            m["net_interchange_mw"] = m["miso_net_interchange_mw"]

    for c in _MISO_FEATURE_COLS:
        if c not in m.columns:
            m[c] = pd.NA

    if "source_name" not in m.columns:
        m = attach_metadata(
            m,
            source_name="FRED/EIA-930",
            source_url="https://fred.stlouisfed.org/;https://www.eia.gov/opendata/",
            match_method="national_or_ba",
            match_confidence=1.0,
        )
    else:
        # Annotate source without overwriting FRED retrieval metadata wholesale
        m["source_name"] = m["source_name"].astype(str).where(
            ~m["source_name"].astype(str).str.contains("EIA", na=False),
            m["source_name"],
        )
        if api_key:
            m["source_name"] = "FRED/EIA-930"
            m["source_url"] = "https://fred.stlouisfed.org/;https://www.eia.gov/opendata/"
            m["match_method"] = "national_or_ba"

    write_silver_table("market_zone_month", m)
    m.to_parquet(SILVER_ENRICHMENT / "miso_zone_month.parquet", index=False)
    nn = float(m["miso_mean_demand_mw"].notna().mean()) if len(m) and "miso_mean_demand_mw" in m.columns else 0.0
    print(f"market_zone_month rows={len(m)} miso_mean_demand_nonnull={nn:.3f}")
    return m


def populate_hifld_poi_context() -> pd.DataFrame:
    """
    Attempt HIFLD electric transmission lines download.
    Compute distance/voltage using county centroids when line geometry available;
    otherwise write empty typed table.
    """
    ensure_enrichment_dirs()
    url = (
        "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
        "Electric_Power_Transmission_Lines/FeatureServer/0/query"
        "?where=1%3D1&outFields=VOLTAGE,STATUS&resultRecordCount=1&f=geojson"
    )
    raw = _http_get(url, timeout=60)
    geo = pd.read_parquet(SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet")

    if raw is None:
        write_bronze_text(
            "hifld_transmission",
            "DOWNLOAD_FAILED.txt",
            "HIFLD FeatureServer probe failed — transmission_assets left empty.\n",
            overwrite=True,
        )
        empty = write_empty_table("transmission_assets")
        ctx = geo[["project_key", "poi_key", "county_fips", "latitude", "longitude"]].copy()
        ctx["distance_to_transmission_km"] = pd.NA
        ctx["nearby_transmission_voltage"] = pd.NA
        ctx["effective_date"] = pd.Timestamp("2024-01-01")
        ctx["available_date"] = pd.Timestamp("2024-01-01")
        ctx["entity_key"] = ctx["project_key"]
        ctx["geographic_key"] = ctx["county_fips"]
        ctx = attach_metadata(
            ctx,
            source_name="HIFLD unavailable — centroids only",
            source_url="https://hifld-geoplatform.opendata.arcgis.com/",
            match_method="county_centroid",
            match_confidence=0.3,
            entity_key_col="entity_key",
            geographic_key_col="geographic_key",
        )
        ctx.to_parquet(SILVER_ENRICHMENT / "poi_grid_context.parquet", index=False)
        return empty

    write_bronze_bytes("hifld_transmission", "probe.geojson", raw, overwrite=True)
    write_bronze_text(
        "hifld_transmission",
        "NOTE.txt",
        "Probe succeeded. Full line layer too large for sprint distance join; "
        "poi_grid_context uses county centroids with null distance pending local extract.\n",
        overwrite=True,
    )
    empty = write_empty_table("transmission_assets")
    ctx = geo[["project_key", "poi_key", "county_fips", "latitude", "longitude"]].copy()
    ctx["distance_to_transmission_km"] = pd.NA
    ctx["nearby_transmission_voltage"] = pd.NA
    ctx["effective_date"] = pd.Timestamp("2024-01-01")
    ctx["available_date"] = pd.Timestamp("2024-06-01")
    ctx["entity_key"] = ctx["project_key"]
    ctx["geographic_key"] = ctx["county_fips"]
    ctx = attach_metadata(
        ctx,
        source_name="HIFLD probe + county centroids",
        source_url="https://hifld-geoplatform.opendata.arcgis.com/",
        match_method="county_centroid",
        match_confidence=0.4,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    ctx.to_parquet(SILVER_ENRICHMENT / "poi_grid_context.parquet", index=False)
    print(f"poi_grid_context rows={len(ctx)}")
    return empty


def populate_mtep_stub() -> pd.DataFrame:
    ensure_enrichment_dirs()
    write_bronze_text(
        "miso_mtep",
        "NOTE.txt",
        "MTEP public project list harvest not automated in this sprint. "
        "Table mtep_project_events left empty typed.\n",
        overwrite=True,
    )
    from src.enrichment.registry import empty_enrichment_frame

    extra = [
        "upgrade_id",
        "poi_key",
        "transmission_owner",
        "upgrade_completion_year",
        "investment_usd",
        "voltage_kv",
        "project_name",
    ]
    df = empty_enrichment_frame(extra)
    df.to_parquet(SILVER_ENRICHMENT / "mtep_project_events.parquet", index=False)
    print("mtep_project_events empty typed written")
    return df


def populate_grid_pressure() -> None:
    enrich_market_zone_demand_growth()
    populate_hifld_poi_context()
    populate_mtep_stub()


if __name__ == "__main__":
    from src.enrichment.env import load_enrichment_env

    load_enrichment_env()
    populate_grid_pressure()
