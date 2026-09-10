"""EIA-860M monthly generator inventory → silver planned-COD shifts.

Downloads public monthly Excel files when possible. GIQ matching is fuzzy
(state + county + MW + fuel + planned year). Failures leave an empty typed table.
"""

from __future__ import annotations

import calendar
import json
import re
from io import BytesIO
from typing import Any
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_silver_table,
)

SOURCE_ID = "eia_860m"
SOURCE_URL = "https://www.eia.gov/electricity/data/eia860m/"
MISO_STATES = {
    "AR", "IL", "IN", "IA", "KY", "LA", "MI", "MN", "MS", "MO", "MT", "ND", "SD", "TX", "WI",
}
EXTRA_COLS = [
    "plant_id",
    "plant_name",
    "generator_id",
    "state_code",
    "county_name",
    "nameplate_mw",
    "fuel",
    "technology",
    "status",
    "planned_month",
    "planned_year",
    "planned_cod",
    "operating_month",
    "operating_year",
    "snapshot_year",
    "snapshot_month",
]


def _http_get(url: str, timeout: int = 90) -> bytes | None:
    req = Request(url, headers={"User-Agent": "team8-miso-queue/0.1 (research)"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def candidate_urls(years: range | list[int], months: range | list[int]) -> list[tuple[str, int, int]]:
    names = [calendar.month_name[m].lower() for m in months]
    out: list[tuple[str, int, int]] = []
    for year in years:
        for month, name in zip(months, names, strict=False):
            fname = f"{name}_generator{year}.xlsx"
            out.append((f"https://www.eia.gov/electricity/data/eia860m/xls/{fname}", year, month))
            out.append((f"https://www.eia.gov/electricity/data/eia860m/archive/xls/{fname}", year, month))
    return out


def _find_col(cols: list[str], *needles: str) -> str | None:
    lowered = {re.sub(r"[^a-z0-9]+", " ", str(c).lower()).strip(): c for c in cols}
    for n in needles:
        n = re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()
        for k, orig in lowered.items():
            if n == k or n in k:
                return orig
    return None


def parse_860m_workbook(content: bytes, *, year: int, month: int) -> pd.DataFrame:
    try:
        xl = pd.ExcelFile(BytesIO(content))
    except Exception:
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        sl = str(sheet).lower()
        if sl.endswith("_pr"):
            continue
        # Planned / proposed only (under-construction lives here). Skip Operating/Retired.
        if not any(k in sl for k in ("proposed", "planned")):
            continue
        try:
            raw = pd.read_excel(xl, sheet_name=sheet, header=2)
        except Exception:
            continue
        if raw.empty or len(raw.columns) < 5:
            continue
        cols = [str(c) for c in raw.columns]
        if not any("plant" in c.lower() for c in cols):
            continue
        plant_id = _find_col(cols, "plant id", "plantid")
        plant = _find_col(cols, "plant name", "plant")
        gen = _find_col(cols, "generator id", "generatorid")
        state = _find_col(cols, "plant state", "state")
        county = _find_col(cols, "county")
        mw = _find_col(cols, "nameplate capacity", "nameplate", "nameplate mw")
        fuel = _find_col(cols, "energy source code", "energy source", "fuel")
        tech = _find_col(cols, "technology")
        status = _find_col(cols, "status")
        pmonth = _find_col(cols, "planned operation month", "planned month", "effective month")
        pyear = _find_col(cols, "planned operation year", "planned year", "effective year")
        omonth = _find_col(cols, "operating month")
        oyear = _find_col(cols, "operating year")
        if state is None or mw is None:
            continue
        part = pd.DataFrame(
            {
                "plant_id": raw[plant_id] if plant_id else pd.NA,
                "plant_name": raw[plant] if plant else pd.NA,
                "generator_id": raw[gen] if gen else pd.NA,
                "state_code": raw[state].astype(str).str.upper().str.strip().str[:2],
                "county_name": raw[county].astype(str).str.strip() if county else pd.NA,
                "nameplate_mw": pd.to_numeric(raw[mw], errors="coerce"),
                "fuel": raw[fuel].astype(str) if fuel else pd.NA,
                "technology": raw[tech].astype(str) if tech else pd.NA,
                "status": raw[status].astype(str) if status else sheet,
                "planned_month": pd.to_numeric(raw[pmonth], errors="coerce") if pmonth else pd.NA,
                "planned_year": pd.to_numeric(raw[pyear], errors="coerce") if pyear else pd.NA,
                "operating_month": pd.to_numeric(raw[omonth], errors="coerce") if omonth else pd.NA,
                "operating_year": pd.to_numeric(raw[oyear], errors="coerce") if oyear else pd.NA,
                "sheet": sheet,
            }
        )
        part["snapshot_year"] = year
        part["snapshot_month"] = month
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df[df["state_code"].isin(MISO_STATES)].copy()
    ym = pd.to_numeric(df["planned_year"], errors="coerce")
    mm = pd.to_numeric(df["planned_month"], errors="coerce").fillna(6).clip(1, 12)
    df["planned_cod"] = pd.to_datetime(
        {"year": ym, "month": mm.astype("Int64"), "day": 1},
        errors="coerce",
    )
    df["available_date"] = pd.Timestamp(year=year, month=month, day=1)
    df["effective_date"] = df["available_date"]
    df["entity_key"] = (
        df["plant_id"].astype(str)
        + "|"
        + df["generator_id"].astype(str)
        + "|"
        + df["state_code"].astype(str)
    )
    df["geographic_key"] = df["state_code"].astype(str) + "|" + df["county_name"].astype(str)
    return df


def planned_cod_shifts(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty or "planned_cod" not in monthly.columns:
        return monthly
    df = monthly.sort_values(["entity_key", "available_date"]).copy()
    df["previous_planned_cod"] = df.groupby("entity_key")["planned_cod"].shift(1)
    df["eia_planned_cod_shift_months"] = [
        None
        if pd.isna(a) or pd.isna(b)
        else (pd.Timestamp(a).year - pd.Timestamp(b).year) * 12
        + (pd.Timestamp(a).month - pd.Timestamp(b).month)
        for a, b in zip(df["planned_cod"], df["previous_planned_cod"], strict=False)
    ]
    return df


def match_giq(monthly: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """Fuzzy match EIA proposed units to GIQ projects (state, county, MW, year)."""
    if monthly.empty:
        return pd.DataFrame()
    s = snaps.copy()
    s["observation_date"] = pd.to_datetime(s["observation_date"])
    s["state_code"] = s["state_code"].astype(str).str.upper().str.strip()
    s["capacity_mw"] = pd.to_numeric(s["capacity_mw"], errors="coerce")
    s["county"] = s.get("county_name", pd.Series([pd.NA] * len(s))).astype(str).str.lower().str.strip()
    e = monthly.copy()
    e["county"] = e["county_name"].astype(str).str.lower().str.strip()
    e["mw_bin"] = (pd.to_numeric(e["nameplate_mw"], errors="coerce") / 10.0).round() * 10
    s["mw_bin"] = (s["capacity_mw"] / 10.0).round() * 10
    e["py"] = pd.to_datetime(e["planned_cod"], errors="coerce").dt.year
    s["py"] = pd.to_datetime(s.get("proposed_service_date"), errors="coerce").dt.year
    e2 = e.dropna(subset=["state_code", "mw_bin"])
    s2 = s.dropna(subset=["state_code", "mw_bin"])
    # Snapshots often lack county_name; match state + 10 MW bin, then keep unique pairs.
    m = e2.merge(
        s2[["project_key", "state_code", "mw_bin"]].drop_duplicates(),
        on=["state_code", "mw_bin"],
        how="left",
    )
    dup = m["project_key"].notna() & m.duplicated(["entity_key", "available_date"], keep=False)
    m.loc[dup, "project_key"] = pd.NA
    m["match_method"] = np.where(m["project_key"].notna(), "state_mw10", "unmatched")
    m["match_confidence"] = np.where(m["project_key"].notna(), 0.35, 0.0)
    return m


def _bronze_xlsx(year: int, month: int):
    fname = f"{calendar.month_name[month].lower()}_generator{year}.xlsx"
    return bronze_dir(SOURCE_ID) / fname


def _parse_one_snapshot(*, year: int, month: int, overwrite: bool) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Prefer local bronze xlsx; skip HTML stubs under 100KB; HTTP only if bronze missing."""
    rec: dict[str, Any] = {"year": year, "month": month, "source": None, "bytes": 0, "rows": 0}
    path = _bronze_xlsx(year, month)
    content = None
    if path.exists() and path.stat().st_size >= 100_000:
        content = path.read_bytes()
        rec["source"] = f"bronze:{path.name}"
        rec["bytes"] = int(len(content))
        print(f"  bronze {path.name}", flush=True)
    else:
        for url, y, m in candidate_urls([year], [month]):
            print(f"  GET {url}", flush=True)
            blob = _http_get(url)
            rec["url"] = url
            rec["bytes"] = 0 if blob is None else len(blob)
            if not blob or len(blob) < 100_000:
                continue
            content = blob
            rec["source"] = url
            fname = f"{calendar.month_name[month].lower()}_generator{year}.xlsx"
            try:
                write_bronze_bytes(SOURCE_ID, fname, content, overwrite=overwrite)
            except Exception as exc:  # noqa: BLE001
                rec["bronze_error"] = str(exc)
            break
    if not content:
        rec["rows"] = 0
        rec["note"] = "missing or stub"
        return pd.DataFrame(), rec
    parsed = parse_860m_workbook(content, year=year, month=month)
    rec["rows"] = int(len(parsed))
    return parsed, rec


def run_eia860m_harvest(
    *,
    years: list[int] | None = None,
    months: list[int] | None = None,
    overwrite: bool = True,
) -> dict[str, Any]:
    ensure_enrichment_dirs()
    years = years or [2022, 2023, 2024, 2025, 2026]
    months = months or [3, 6, 9, 12]
    inventory: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    seen: set[tuple[int, int]] = set()
    for year in years:
        for month in months:
            if (year, month) in seen:
                continue
            parsed, rec = _parse_one_snapshot(year=year, month=month, overwrite=overwrite)
            inventory.append(rec)
            if len(parsed):
                seen.add((year, month))
                frames.append(parsed)

    if not frames:
        bronze = bronze_dir(SOURCE_ID)
        for path in sorted(bronze.glob("*.xlsx")):
            if path.stat().st_size < 100_000:
                continue
            try:
                content = path.read_bytes()
                # infer year/month from filename like december_generator2024.xlsx
                import re as _re

                m = _re.search(r"([a-z]+)_generator(\d{4})", path.name.lower())
                if not m:
                    continue
                month_name, year_s = m.group(1), int(m.group(2))
                month = {calendar.month_name[i].lower(): i for i in range(1, 13)}.get(month_name)
                if not month:
                    continue
                parsed = parse_860m_workbook(content, year=year_s, month=month)
                print(f"  bronze parse {path.name} rows={len(parsed)}", flush=True)
                if len(parsed):
                    frames.append(parsed)
            except Exception as exc:  # noqa: BLE001
                print(f"  bronze parse failed {path.name}: {exc}", flush=True)
    if not frames:
        summary = {
            "status": "empty",
            "n": 0,
            "n_monthly": 0,
            "inventory": inventory,
            "note": "No EIA-860M workbooks parsed; silver monthly not overwritten.",
        }
        (ENRICHMENT_REPORTS / "eia_860m_harvest_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print("eia_860m_monthly skipped: 0 snapshots", flush=True)
        return summary

    monthly = pd.concat(frames, ignore_index=True)
    monthly = planned_cod_shifts(monthly)
    monthly = attach_metadata(
        monthly,
        source_name="EIA-860M",
        source_url=SOURCE_URL,
        match_method="direct",
        match_confidence=1.0,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    write_silver_table("eia_860m_monthly", monthly)

    snaps_path = SILVER_DIR / "snapshots" / "project_snapshots.parquet"
    matched_n = 0
    if snaps_path.exists():
        snaps = pd.read_parquet(snaps_path)
        matched = match_giq(monthly, snaps)
        matched = attach_metadata(
            matched,
            source_name="EIA-860M",
            source_url=SOURCE_URL,
            match_method="state_county_mw10_year",
            match_confidence=0.55,
        )
        write_silver_table("eia_860m_giq_matched", matched)
        matched_n = int(matched["project_key"].notna().sum()) if "project_key" in matched.columns else 0

    summary = {
        "status": "ok",
        "n_monthly": int(len(monthly)),
        "n_matched_giq": matched_n,
        "snapshots": sorted({(int(y), int(m)) for y, m in zip(monthly["snapshot_year"], monthly["snapshot_month"], strict=False)}),
        "inventory": inventory,
        "retrieved_at": utc_now_iso(),
    }
    (ENRICHMENT_REPORTS / "eia_860m_harvest_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"eia_860m_monthly n={len(monthly)} giq_matched={matched_n}")
    return summary


if __name__ == "__main__":
    run_eia860m_harvest()
