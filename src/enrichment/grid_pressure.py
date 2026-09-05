"""Grid-pressure enrichment: EIA-930 hourly MISO demand/generation, HIFLD/MTEP context."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

import numpy as np
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

# Approximate WGS84 envelopes for MISO-footprint states (xmin, ymin, xmax, ymax).
_MISO_STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    "AR": (-94.62, 33.00, -89.64, 36.50),
    "IA": (-96.64, 40.38, -90.14, 43.50),
    "IL": (-91.51, 36.97, -87.02, 42.51),
    "IN": (-88.10, 37.77, -84.78, 41.76),
    "KY": (-89.57, 36.50, -81.96, 39.15),
    "LA": (-94.04, 28.93, -88.82, 33.02),
    "MI": (-90.42, 41.70, -82.12, 48.31),
    "MN": (-97.24, 43.50, -89.49, 49.38),
    "MO": (-95.77, 35.995, -89.10, 40.61),
    "MS": (-91.66, 30.17, -88.10, 35.00),
    "MT": (-116.05, 44.36, -104.04, 49.00),
    "ND": (-104.05, 45.94, -96.55, 49.00),
    "OH": (-84.82, 38.40, -80.52, 41.98),
    "SD": (-104.06, 42.48, -96.45, 45.95),
    "TX": (-106.65, 25.84, -93.51, 36.50),
    "WI": (-92.89, 42.49, -86.25, 47.31),
}

_HIFLD_FS_QUERY = (
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/"
    "Electric_Power_Transmission_Lines/FeatureServer/0/query"
)
_HIFLD_PAGE = 2000


def _haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2.0) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def _geojson_line_points(geom: dict) -> list[tuple[float, float]]:
    """Flatten GeoJSON LineString / MultiLineString to (lon, lat) vertices."""
    if not geom:
        return []
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    pts: list[tuple[float, float]] = []
    if gtype == "LineString":
        for c in coords:
            if len(c) >= 2:
                pts.append((float(c[0]), float(c[1])))
    elif gtype == "MultiLineString":
        for line in coords:
            for c in line:
                if len(c) >= 2:
                    pts.append((float(c[0]), float(c[1])))
    return pts


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
    Paginate HIFLD electric transmission lines for MISO-state envelopes,
    write transmission_assets, and compute project distance_to_transmission_km.
    """
    ensure_enrichment_dirs()
    from src.enrichment.registry import utc_now_iso

    retrieved_at = utc_now_iso()
    geo = pd.read_parquet(SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet")

    all_features: list[dict] = []
    page_bytes = 0
    for st, (xmin, ymin, xmax, ymax) in _MISO_STATE_BBOX.items():
        offset = 0
        while True:
            params = urllib.parse.urlencode(
                {
                    "where": "1=1",
                    "geometry": f"{xmin},{ymin},{xmax},{ymax}",
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "OBJECTID,ID,VOLTAGE,STATUS,OWNER,SUB_1,SUB_2,VOLT_CLASS,SOURCEDATE,VAL_DATE",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(_HIFLD_PAGE),
                }
            )
            url = f"{_HIFLD_FS_QUERY}?{params}"
            raw = _http_get(url, timeout=180)
            if raw is None:
                write_bronze_text(
                    "hifld_transmission",
                    f"download_failed_{st}_offset_{offset}.txt",
                    f"Failed query for state={st} offset={offset}\n",
                    overwrite=True,
                )
                break
            page_bytes += len(raw)
            write_bronze_bytes(
                "hifld_transmission",
                f"lines_{st}_offset_{offset:06d}.geojson",
                raw,
                overwrite=True,
            )
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                write_bronze_text(
                    "hifld_transmission",
                    f"parse_error_{st}_{offset}.txt",
                    str(exc),
                    overwrite=True,
                )
                break
            feats = payload.get("features") or []
            if not feats:
                break
            for feat in feats:
                props = feat.get("properties") or {}
                geom = feat.get("geometry") or {}
                pts = _geojson_line_points(geom)
                if len(pts) < 2:
                    continue
                # Midpoint proxy for asset table
                mid = pts[len(pts) // 2]
                vid = props.get("ID") or props.get("OBJECTID")
                all_features.append(
                    {
                        "asset_id": str(vid) if vid is not None else None,
                        "upgrade_id": str(vid) if vid is not None else None,
                        "voltage_kv": props.get("VOLTAGE"),
                        "volt_class": props.get("VOLT_CLASS"),
                        "status": props.get("STATUS"),
                        "transmission_owner": props.get("OWNER"),
                        "sub_1": props.get("SUB_1"),
                        "sub_2": props.get("SUB_2"),
                        "source_date_ms": props.get("SOURCEDATE"),
                        "val_date_ms": props.get("VAL_DATE"),
                        "state_query": st,
                        "mid_lon": mid[0],
                        "mid_lat": mid[1],
                        "n_vertices": len(pts),
                        "_pts": pts,
                    }
                )
            print(f"  HIFLD {st} offset={offset} feats={len(feats)} kept_total={len(all_features)}")
            if len(feats) < _HIFLD_PAGE:
                break
            offset += _HIFLD_PAGE
            if offset > 50000:
                break

    # Deduplicate by asset_id (state envelopes overlap)
    assets_raw = pd.DataFrame(all_features)
    if len(assets_raw) and "asset_id" in assets_raw.columns:
        assets_raw = assets_raw.drop_duplicates("asset_id", keep="first")

    # Layer vintage for PIT: prefer early validation dates from features; fall back to 2020-01-01.
    vintage = pd.Timestamp("2020-01-01")
    if len(assets_raw):
        for col in ("val_date_ms", "source_date_ms"):
            if col not in assets_raw.columns:
                continue
            ms = pd.to_numeric(assets_raw[col], errors="coerce").dropna()
            if len(ms):
                dates = pd.to_datetime(ms, unit="ms", errors="coerce").dropna()
                if len(dates):
                    vintage = pd.Timestamp(dates.quantile(0.25).date())
                    break
    available_date = vintage
    retrieve_day = pd.Timestamp(retrieved_at[:10])
    if available_date > retrieve_day:
        available_date = retrieve_day
    print(f"  HIFLD PIT available_date vintage={available_date.date()}")

    if assets_raw.empty:
        write_bronze_text(
            "hifld_transmission",
            "DOWNLOAD_FAILED.txt",
            "HIFLD paginated MISO-state queries returned no features.\n",
            overwrite=True,
        )
        empty = write_empty_table("transmission_assets")
        ctx = geo[["project_key", "poi_key", "county_fips", "latitude", "longitude"]].copy()
        ctx["distance_to_transmission_km"] = pd.NA
        ctx["nearby_transmission_voltage"] = pd.NA
        ctx["effective_date"] = available_date
        ctx["available_date"] = available_date
        ctx["entity_key"] = ctx["project_key"]
        ctx["geographic_key"] = ctx["county_fips"]
        ctx = attach_metadata(
            ctx,
            source_name="HIFLD unavailable",
            source_url="https://hifld-geoplatform.opendata.arcgis.com/",
            retrieved_at=retrieved_at,
            match_method="county_centroid",
            match_confidence=0.3,
            entity_key_col="entity_key",
            geographic_key_col="geographic_key",
        )
        ctx.to_parquet(SILVER_ENRICHMENT / "poi_grid_context.parquet", index=False)
        return empty

    # Build per-state point indexes for nearest-line distance (vertex/midpoint approximation)
    pts_by_state: dict[str, np.ndarray] = {}
    volts_by_state: dict[str, list] = {}
    for st, grp in assets_raw.groupby("state_query"):
        line_pts: list[tuple[float, float, float | None]] = []
        for _, row in grp.iterrows():
            volt = row.get("voltage_kv")
            pts = row["_pts"] if isinstance(row["_pts"], list) else []
            if not pts:
                continue
            step = max(1, len(pts) // 15)
            for lon, lat in pts[::step]:
                line_pts.append((float(lat), float(lon), volt))
            for lon, lat in (pts[0], pts[len(pts) // 2], pts[-1]):
                line_pts.append((float(lat), float(lon), volt))
        if not line_pts:
            continue
        pts_by_state[str(st)] = np.asarray([[p[0], p[1]] for p in line_pts], dtype=float)
        volts_by_state[str(st)] = [p[2] for p in line_pts]

    # National fallback pool (limited) for projects missing state
    all_pts = (
        np.vstack(list(pts_by_state.values()))
        if pts_by_state
        else np.zeros((0, 2))
    )
    all_volts: list = []
    for st in pts_by_state:
        all_volts.extend(volts_by_state[st])

    distances: list[float | object] = []
    near_v: list[float | object] = []
    for _, prow in geo.iterrows():
        lat = prow.get("latitude")
        lon = prow.get("longitude")
        st = prow.get("state_code")
        if pd.isna(lat) or pd.isna(lon):
            distances.append(pd.NA)
            near_v.append(pd.NA)
            continue
        pts_arr = pts_by_state.get(str(st)) if pd.notna(st) else None
        volts_arr = volts_by_state.get(str(st)) if pd.notna(st) else None
        if pts_arr is None or pts_arr.shape[0] == 0:
            pts_arr = all_pts
            volts_arr = all_volts
        if pts_arr is None or pts_arr.shape[0] == 0:
            distances.append(pd.NA)
            near_v.append(pd.NA)
            continue
        best_i = 0
        best_d = float("inf")
        lat0 = float(lat)
        lon0 = float(lon)
        chunk = 8000
        for start in range(0, len(pts_arr), chunk):
            sl = pts_arr[start : start + chunk]
            d = _haversine_km(lat0, lon0, sl[:, 0], sl[:, 1])
            i = int(np.argmin(d))
            if float(d[i]) < best_d:
                best_d = float(d[i])
                best_i = start + i
        distances.append(best_d)
        near_v.append(volts_arr[best_i] if volts_arr is not None and best_i < len(volts_arr) else pd.NA)

    assets = assets_raw.drop(columns=["_pts"], errors="ignore").copy()
    assets["voltage_kv"] = pd.to_numeric(assets.get("voltage_kv"), errors="coerce")
    assets["effective_date"] = available_date
    assets["available_date"] = available_date
    assets["entity_key"] = assets["asset_id"]
    assets["geographic_key"] = assets["state_query"]
    assets["poi_key"] = pd.NA
    assets["upgrade_completion_year"] = pd.NA
    assets["investment_usd"] = pd.NA
    assets["distance_to_transmission_km"] = pd.NA
    assets = attach_metadata(
        assets,
        source_name="HIFLD Electric Power Transmission Lines",
        source_url="https://hifld-geoplatform.opendata.arcgis.com/",
        retrieved_at=retrieved_at,
        match_method="miso_state_bbox_pagination",
        match_confidence=0.85,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    write_silver_table("transmission_assets", assets)
    assets.to_parquet(SILVER_ENRICHMENT / "transmission_assets.parquet", index=False)

    ctx = geo[["project_key", "poi_key", "county_fips", "latitude", "longitude"]].copy()
    ctx["distance_to_transmission_km"] = distances
    ctx["nearby_transmission_voltage"] = near_v
    ctx["effective_date"] = available_date
    ctx["available_date"] = available_date
    ctx["entity_key"] = ctx["project_key"]
    ctx["geographic_key"] = ctx["county_fips"]
    ctx = attach_metadata(
        ctx,
        source_name="HIFLD + county centroids",
        source_url="https://hifld-geoplatform.opendata.arcgis.com/",
        retrieved_at=retrieved_at,
        match_method="nearest_line_vertex_haversine",
        match_confidence=0.75,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    ctx.to_parquet(SILVER_ENRICHMENT / "poi_grid_context.parquet", index=False)
    nn = float(pd.Series(distances).notna().mean()) if distances else 0.0
    write_bronze_text(
        "hifld_transmission",
        "NOTE.txt",
        f"Paginated MISO-state HIFLD extract: assets={len(assets)} bytes≈{page_bytes} "
        f"poi_distance_nonnull={nn:.3f}\n",
        overwrite=True,
    )
    print(f"transmission_assets={len(assets)} poi_grid_context={len(ctx)} distance_nonnull={nn:.3f}")
    return assets


def populate_mtep_stub() -> pd.DataFrame:
    """Deprecated stub — prefer ingest_mtep.run_mtep_harvest."""
    from src.enrichment.ingest_mtep import run_mtep_harvest

    return run_mtep_harvest()


def populate_grid_pressure() -> None:
    enrich_market_zone_demand_growth()
    populate_hifld_poi_context()
    populate_mtep_stub()


if __name__ == "__main__":
    from src.enrichment.env import load_enrichment_env

    load_enrichment_env()
    populate_grid_pressure()
