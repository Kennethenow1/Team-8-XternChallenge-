"""Harvest MISO MTEP Appendix A project lists into mtep_project_events."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    empty_enrichment_frame,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
)

SOURCE_ID = "miso_mtep"
MTEP_PAGE = "https://www.misoenergy.org/planning/transmission-planning/mtep/"

# Public CDN assets discovered from the MTEP planning page.
DEFAULT_ASSETS = [
    {
        "name": "appendix_a_status_report.xlsx",
        "url": "https://cdn.misoenergy.org/Appendix%20A%20Status%20Report575959.xlsx",
        "kind": "status",
        "header_row": 2,
    },
    {
        "name": "appendix_a_in_service.xlsx",
        "url": "https://cdn.misoenergy.org/MTEP%20Appendix%20A%20In%20Service%20Projects106330.xlsx",
        "kind": "in_service",
        "header_row": 1,
    },
    {
        "name": "mtep_projects_under_evaluation.xlsx",
        "url": "https://cdn.misoenergy.org/MTEP%20Projects%20Under%20Evaluation368757.xlsx",
        "kind": "under_evaluation",
        "header_row": None,  # auto-detect
    },
]

_EXTRA_COLS = [
    "upgrade_id",
    "project_key",
    "poi_key",
    "transmission_owner",
    "upgrade_completion_year",
    "investment_usd",
    "voltage_kv",
    "project_name",
    "planning_region",
    "mtep_cycle",
    "state_code",
    "county_fips",
    "planning_status",
    "facility_name",
]


def _http_get(url: str, timeout: int = 120) -> bytes | None:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Team8-MISO-Enrichment/1.0)"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  mtep download failed: {exc}")
        return None


def _norm_col(c: Any) -> str:
    return re.sub(r"\s+", " ", str(c).strip().lower())


def _find_col(cols: list[str], *needles: str) -> str | None:
    for c in cols:
        cl = _norm_col(c)
        if all(n.lower() in cl for n in needles):
            return c
    return None


def _detect_header_row(raw: bytes, max_scan: int = 8) -> int:
    for h in range(max_scan):
        try:
            df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=h, nrows=2)
        except Exception:  # noqa: BLE001
            continue
        cols = [_norm_col(c) for c in df.columns]
        joined = " | ".join(cols)
        if "mtep project" in joined or ("project" in joined and "submitting" in joined):
            return h
    return 0


def _parse_money(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[\$,]", "", str(val)).strip()
    try:
        return float(s)
    except Exception:  # noqa: BLE001
        return None


def _year_from(val: Any) -> int | None:
    if val is None or pd.isna(val):
        return None
    ts = pd.to_datetime(val, errors="coerce")
    if pd.notna(ts):
        return int(ts.year)
    m = re.search(r"(20\d{2})", str(val))
    return int(m.group(1)) if m else None


def _parse_workbook(raw: bytes, *, kind: str, header_row: int | None, source_url: str, asof: pd.Timestamp) -> pd.DataFrame:
    h = header_row if header_row is not None else _detect_header_row(raw)
    df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=h)
    df = df.dropna(how="all")
    cols = list(df.columns)

    id_col = (
        _find_col(cols, "mtep project id")
        or _find_col(cols, "project id")
        or _find_col(cols, "facility id")
    )
    name_col = (
        _find_col(cols, "project name")
        or _find_col(cols, "project")
        or _find_col(cols, "name")
    )
    to_col = _find_col(cols, "submitting to") or _find_col(cols, "transmission owner")
    region_col = _find_col(cols, "planning region")
    cycle_col = _find_col(cols, "target mtep") or _find_col(cols, "mtep cycle")
    cost_col = _find_col(cols, "current cost") or _find_col(cols, "cost")
    isd_col = (
        _find_col(cols, "expected isd")
        or _find_col(cols, "in service")
        or _find_col(cols, "board approved")
    )
    kv_col = _find_col(cols, "max kv") or _find_col(cols, "kv")
    state_col = (
        _find_col(cols, "state(s)")
        or _find_col(cols, "state 1")
        or _find_col(cols, "state")
    )
    state2_col = _find_col(cols, "state 2")
    status_col = _find_col(cols, "planning status") or _find_col(cols, "status")
    fac_col = _find_col(cols, "facility description") or _find_col(cols, "name")
    board_col = _find_col(cols, "board approved")

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        upgrade_id = r.get(id_col) if id_col else None
        project_name = r.get(name_col) if name_col else None
        if pd.isna(upgrade_id) and (project_name is None or pd.isna(project_name)):
            continue
        # Skip leftover section header rows
        if str(upgrade_id).strip().lower() in {"mtep project id", "project level fields", "nan"}:
            continue

        isd_year = _year_from(r.get(isd_col) if isd_col else None)
        cost = _parse_money(r.get(cost_col) if cost_col else None)
        kv = pd.to_numeric(r.get(kv_col), errors="coerce") if kv_col else pd.NA
        state_raw = r.get(state_col) if state_col else None
        if (state_raw is None or pd.isna(state_raw)) and state2_col:
            state_raw = r.get(state2_col)
        state_code = None
        if state_raw is not None and not pd.isna(state_raw):
            m = re.findall(r"\b([A-Z]{2})\b", str(state_raw).upper())
            state_code = m[0] if m else None

        cycle_val = r.get(cycle_col) if cycle_col else None
        board_ts = pd.to_datetime(r.get(board_col), errors="coerce") if board_col else pd.NaT
        isd_ts = pd.to_datetime(r.get(isd_col), errors="coerce") if isd_col else pd.NaT

        # available_date: board approved when known; else MTEP cycle year start; else document asof.
        # Never use future Expected ISD alone as available_date.
        avail = pd.NaT
        if pd.notna(board_ts):
            avail = pd.Timestamp(board_ts)
        else:
            cy = re.search(r"(20\d{2})", str(cycle_val)) if cycle_val is not None and not pd.isna(cycle_val) else None
            if cy:
                avail = pd.Timestamp(f"{cy.group(1)}-01-01")
            else:
                avail = asof
        # Cap available_date at document asof (cannot know future beyond the harvested list)
        if pd.notna(avail) and avail > asof:
            avail = asof

        eff = isd_ts if pd.notna(isd_ts) else avail

        rows.append(
            {
                "upgrade_id": str(upgrade_id).replace(".0", "") if pd.notna(upgrade_id) else None,
                "project_name": None if project_name is None or pd.isna(project_name) else str(project_name),
                "facility_name": None if fac_col is None or pd.isna(r.get(fac_col)) else str(r.get(fac_col))[:500],
                "transmission_owner": None if to_col is None or pd.isna(r.get(to_col)) else str(r.get(to_col)),
                "planning_region": None if region_col is None or pd.isna(r.get(region_col)) else str(r.get(region_col)),
                "mtep_cycle": None if cycle_val is None or pd.isna(cycle_val) else str(cycle_val),
                "investment_usd": cost,
                "voltage_kv": float(kv) if pd.notna(kv) else None,
                "upgrade_completion_year": isd_year,
                "state_code": state_code,
                "planning_status": None if status_col is None or pd.isna(r.get(status_col)) else str(r.get(status_col)),
                "list_kind": kind,
                "effective_date": eff,
                "available_date": avail,
                "source_url": source_url,
            }
        )
    return pd.DataFrame(rows)


def _match_project_keys(events: pd.DataFrame) -> pd.DataFrame:
    """High-confidence match via county FIPS + TO, or state + TO when unique enough; else null project_key."""
    out = events.copy()
    out["project_key"] = pd.NA
    out["poi_key"] = pd.NA
    out["county_fips"] = pd.NA
    out["match_method"] = "unmatched"
    out["match_confidence"] = 0.0

    geo_path = SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet"
    if not geo_path.exists() or out.empty:
        return out
    geo = pd.read_parquet(geo_path)

    # Build TO → projects via developer/utility overlay when present on snapshots attrs is weak;
    # Prefer county_fips state + planning region heuristic later. For now: match by state_code
    # when a single dominant POI text appears in project_name — leave mostly null (honest).
    # County FIPS: extract "X County" from project/facility text and resolve within state.
    from src.enrichment.build_crosswalks import _norm_county, download_census_county_fips

    try:
        fips = download_census_county_fips()
    except Exception:  # noqa: BLE001
        fips = pd.DataFrame()

    by_state: dict[str, pd.DataFrame] = {}
    if len(fips) and "state_code" in fips.columns:
        for st, g in fips.dropna(subset=["county_name_norm", "county_fips"]).groupby("state_code"):
            by_state[str(st)] = g.drop_duplicates("county_name_norm")

    keys: list[object] = []
    methods: list[str] = []
    confs: list[float] = []
    counties: list[object] = []

    geo_by_fips = (
        geo.dropna(subset=["county_fips", "project_key"])
        .groupby("county_fips")["project_key"]
        .apply(list)
        .to_dict()
        if "county_fips" in geo.columns
        else {}
    )

    for _, r in out.iterrows():
        st = r.get("state_code")
        text = " ".join(
            str(x)
            for x in [r.get("project_name"), r.get("facility_name")]
            if x is not None and not (isinstance(x, float) and pd.isna(x))
        )
        m = re.search(r"([A-Za-z .]+)\s+County", text, re.I)
        county_fips = None
        if m and st and st in by_state:
            nn = _norm_county(m.group(1))
            pool = by_state[st]
            hit = pool[pool["county_name_norm"] == nn]
            if len(hit):
                county_fips = str(hit["county_fips"].iloc[0]).zfill(5)

        counties.append(county_fips)
        if county_fips and county_fips in geo_by_fips:
            # Do not invent a single project_key when many queue projects share the county —
            # leave project_key null; county_fips enables Gold county pressure features.
            keys.append(None)
            methods.append("county_fips_from_name")
            confs.append(0.7)
        else:
            keys.append(None)
            methods.append("geographic_only" if county_fips or st else "unmatched")
            confs.append(0.4 if county_fips or st else 0.0)

    out["project_key"] = keys
    out["county_fips"] = counties
    out["match_method_row"] = methods
    out["match_confidence_row"] = confs
    return out


def run_mtep_harvest() -> pd.DataFrame:
    ensure_enrichment_dirs()
    retrieved_at = utc_now_iso()
    bronze = bronze_dir(SOURCE_ID)
    inventory: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []

    # Document as-of: prefer date embedded in status-report title cell when present; else retrieve day.
    asof = pd.Timestamp(retrieved_at[:10])

    for asset in DEFAULT_ASSETS:
        raw = _http_get(asset["url"])
        status = "ok" if raw else "failed"
        inventory.append({"name": asset["name"], "url": asset["url"], "status": status, "bytes": len(raw or b"")})
        if not raw:
            continue
        write_bronze_bytes(SOURCE_ID, asset["name"], raw, overwrite=True)
        # Try to read report-through date from first cells of status report
        if asset["kind"] == "status":
            try:
                preview = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None, nrows=1)
                for v in preview.iloc[0].tolist():
                    ts = pd.to_datetime(v, errors="coerce")
                    if pd.notna(ts):
                        asof = pd.Timestamp(ts)
                        break
            except Exception:  # noqa: BLE001
                pass
        try:
            part = _parse_workbook(
                raw,
                kind=asset["kind"],
                header_row=asset.get("header_row"),
                source_url=asset["url"],
                asof=asof,
            )
            frames.append(part)
            print(f"  mtep {asset['name']}: rows={len(part)}")
        except Exception as exc:  # noqa: BLE001
            write_bronze_text(SOURCE_ID, f"parse_error_{asset['name']}.txt", str(exc), overwrite=True)
            print(f"  mtep parse failed {asset['name']}: {exc}")

    inv_df = pd.DataFrame(inventory)
    inv_df.to_csv(bronze / "mtep_harvest_inventory.csv", index=False)
    ENRICHMENT_REPORTS.mkdir(parents=True, exist_ok=True)
    inv_df.to_csv(ENRICHMENT_REPORTS / "mtep_harvest_inventory.csv", index=False)

    if not frames:
        write_bronze_text(
            SOURCE_ID,
            "NOTE.txt",
            "No MTEP structured lists downloaded/parsed; mtep_project_events left empty typed.\n",
            overwrite=True,
        )
        df = empty_enrichment_frame(_EXTRA_COLS)
        df.to_parquet(SILVER_ENRICHMENT / "mtep_project_events.parquet", index=False)
        summary = {"events": 0, "matched_project_keys": 0, "inventory": inventory}
        (ENRICHMENT_REPORTS / "mtep_harvest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("mtep_project_events empty typed written")
        return df

    events = pd.concat(frames, ignore_index=True)
    events = events.drop_duplicates(subset=["upgrade_id", "list_kind", "facility_name"], keep="first")
    events = _match_project_keys(events)
    events["entity_key"] = events["upgrade_id"]
    events["geographic_key"] = events["county_fips"].fillna(events["state_code"])
    events["poi_key"] = events.get("poi_key")
    events = attach_metadata(
        events,
        source_name="MISO MTEP Appendix A",
        source_url=MTEP_PAGE,
        retrieved_at=retrieved_at,
        match_method="county_or_state_from_list",
        match_confidence=0.6,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    # Restore per-row match diagnostics computed before attach_metadata overwrite.
    if "match_method_row" in events.columns:
        events["match_method"] = events["match_method_row"]
        events = events.drop(columns=["match_method_row"])
    if "match_confidence_row" in events.columns:
        events["match_confidence"] = events["match_confidence_row"]
        events = events.drop(columns=["match_confidence_row"])
    events.to_parquet(SILVER_ENRICHMENT / "mtep_project_events.parquet", index=False)

    n_matched = int(events["project_key"].notna().sum()) if "project_key" in events.columns else 0
    n_county = int(events["county_fips"].notna().sum()) if "county_fips" in events.columns else 0
    summary = {
        "events": int(len(events)),
        "matched_project_keys": n_matched,
        "with_county_fips": n_county,
        "asof_date": str(asof.date()),
        "inventory": inventory,
        "retrieved_at": retrieved_at,
    }
    (ENRICHMENT_REPORTS / "mtep_harvest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("events", "matched_project_keys", "with_county_fips")}, indent=2))
    return events


if __name__ == "__main__":
    run_mtep_harvest()
