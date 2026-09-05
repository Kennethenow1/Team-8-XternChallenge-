"""Correct study_events naming: queue snapshot vs historical DPP events."""

from __future__ import annotations

import csv
import re
import urllib.request
from pathlib import Path

import pandas as pd

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    empty_enrichment_frame,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
    write_silver_table,
)
from src.enrichment.skeletons import write_empty_table

HISTORICAL_STUDY_EXTRA = [
    "project_key",
    "source_project_id",
    "study_cycle",
    "study_group",
    "phase",
    "event_date",
    "upgrade_cost_usd",
    "upgrade_cost_per_mw",
    "capacity_mw",
    "source_pdf_url",
    "source_page_ref",
]


def rename_queue_study_status() -> pd.DataFrame:
    """
    Ensure queue_study_status holds current-queue phase snapshot.
    Preserve historical miso_dpp_events / study_events when already populated.
    """
    ensure_enrichment_dirs()
    src = SILVER_ENRICHMENT / "study_events.parquet"
    dpp_path = SILVER_ENRICHMENT / "miso_dpp_events.parquet"

    def _is_historical(df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False
        date_col = "report_date" if "report_date" in df.columns else ("event_date" if "event_date" in df.columns else None)
        n_dates = int(df[date_col].nunique()) if date_col else 0
        key = "project_key" if "project_key" in df.columns else ("project_id" if "project_id" in df.columns else None)
        max_per = int(df.groupby(key).size().max()) if key and len(df) else 0
        src_name = str(df["source_name"].iloc[0]) if "source_name" in df.columns and len(df) else ""
        if "Queue-derived" in src_name or "Queue current" in src_name:
            return False
        if "MISO DPP" in src_name:
            return True
        return n_dates > 1 or max_per > 1 or len(df) > 5000

    historical = None
    if dpp_path.exists():
        dpp = pd.read_parquet(dpp_path)
        if _is_historical(dpp):
            historical = dpp
            print(f"Preserving miso_dpp_events rows={len(dpp)}")
    if historical is None and src.exists():
        df = pd.read_parquet(src)
        if _is_historical(df):
            historical = df
            print(f"Preserving historical study_events rows={len(df)}")
        elif len(df):
            # Queue copy → rename aside
            n_dates = df["report_date"].nunique() if "report_date" in df.columns else 0
            max_per = df.groupby("project_key").size().max() if "project_key" in df.columns else 0
            out_path = SILVER_ENRICHMENT / "queue_study_status.parquet"
            df.to_parquet(out_path, index=False)
            df.to_csv(SILVER_ENRICHMENT / "queue_study_status.csv", index=False)
            print(
                f"Renamed queue copy → queue_study_status "
                f"(rows={len(df)} unique_report_dates={n_dates} max_events/project={max_per})"
            )

    _write_queue_status_from_snaps()

    if historical is not None:
        historical.to_parquet(SILVER_ENRICHMENT / "study_events.parquet", index=False)
        historical.to_parquet(dpp_path, index=False)
        return historical

    empty = empty_enrichment_frame(HISTORICAL_STUDY_EXTRA)
    write_silver_table("study_events", empty)
    empty.to_parquet(dpp_path, index=False)
    return empty


def _write_queue_status_from_snaps() -> pd.DataFrame:
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    miso = snaps[snaps["source_name"] == "MISO"].copy()
    if miso.empty:
        miso = snaps.copy()
    rows = []
    for _, r in miso.iterrows():
        rows.append(
            {
                "project_key": r["project_key"],
                "source_project_id": r.get("source_project_id"),
                "study_cycle": r.get("study_cycle"),
                "study_group": r.get("study_group"),
                "study_phase": r.get("study_phase"),
                "capacity_mw": r.get("capacity_mw"),
                "report_date": r["observation_date"],
                "effective_date": r["observation_date"],
                "available_date": r.get("published_at") or r["observation_date"],
                "entity_key": r["project_key"],
                "geographic_key": r.get("poi_key"),
            }
        )
    out = pd.DataFrame(rows)
    out = attach_metadata(
        out,
        source_name="Queue current study status",
        source_url=None,
        match_method="snapshot_fields",
        match_confidence=1.0,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    out.to_parquet(SILVER_ENRICHMENT / "queue_study_status.parquet", index=False)
    return out


def harvest_miso_dpp_index() -> pd.DataFrame:
    """
    Attempt to list MISO GI study public pages into Bronze harvest_index.
    Does not invent PDF event dates — only records URLs retrieved.
    """
    ensure_enrichment_dirs()
    urls = [
        "https://www.misoenergy.org/planning/generator-interconnection/GI_Studies/",
        "https://www.misoenergy.org/planning/generator-interconnection/",
    ]
    retrieved = utc_now_iso()
    index_rows = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Team8-MISO-Enrichment/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            fname = re.sub(r"[^\w]+", "_", url.strip("/").split("/")[-1]) or "index"
            write_bronze_bytes("miso_dpp_studies", f"{fname}.html", body, overwrite=True)
            text = body.decode("utf-8", errors="replace")
            pdfs = sorted(set(re.findall(r'href=["\']([^"\']+\.pdf)[^"\']*["\']', text, flags=re.I)))
            for p in pdfs[:500]:
                index_rows.append(
                    {
                        "source_page": url,
                        "asset_url": p if p.startswith("http") else url.rsplit("/", 1)[0] + "/" + p.lstrip("/"),
                        "retrieved_at": retrieved,
                        "parse_status": "listed_not_parsed",
                    }
                )
            index_rows.append(
                {
                    "source_page": url,
                    "asset_url": url,
                    "retrieved_at": retrieved,
                    "parse_status": "page_fetched",
                    "n_pdf_links": len(pdfs),
                }
            )
        except Exception as exc:  # noqa: BLE001
            write_bronze_text("miso_dpp_studies", "harvest_error.txt", f"{url}\n{exc}\n", overwrite=True)
            index_rows.append(
                {
                    "source_page": url,
                    "asset_url": None,
                    "retrieved_at": retrieved,
                    "parse_status": f"failed:{exc}",
                }
            )

    idx = pd.DataFrame(index_rows)
    bronze = bronze_dir("miso_dpp_studies")
    idx.to_csv(bronze / "harvest_index.csv", index=False)
    print(f"DPP harvest_index rows={len(idx)}")
    # Do not wipe historical DPP events produced by ingest_miso_dpp.
    existing = SILVER_ENRICHMENT / "miso_dpp_events.parquet"
    if existing.exists():
        cur = pd.read_parquet(existing)
        if len(cur) > 0:
            print(f"Preserving existing miso_dpp_events rows={len(cur)}")
            return idx
    empty = empty_enrichment_frame(HISTORICAL_STUDY_EXTRA)
    write_silver_table("study_events", empty)
    empty.to_parquet(SILVER_ENRICHMENT / "miso_dpp_events.parquet", index=False)
    return idx


def study_honesty_metrics() -> dict:
    qpath = SILVER_ENRICHMENT / "queue_study_status.parquet"
    spath = SILVER_ENRICHMENT / "study_events.parquet"
    q = pd.read_parquet(qpath) if qpath.exists() else pd.DataFrame()
    s = pd.read_parquet(spath) if spath.exists() else pd.DataFrame()
    harvest = bronze_dir("miso_dpp_studies") / "harvest_index.csv"
    n_pdf = 0
    if harvest.exists():
        h = pd.read_csv(harvest)
        n_pdf = int(h["asset_url"].astype(str).str.lower().str.endswith(".pdf").sum()) if "asset_url" in h.columns else 0
    metrics = {
        "queue_study_status_rows": len(q),
        "queue_unique_report_dates": int(q["report_date"].nunique()) if len(q) and "report_date" in q.columns else 0,
        "queue_max_events_per_project": int(q.groupby("project_key").size().max()) if len(q) and "project_key" in q.columns else 0,
        "historical_study_events_rows": len(s),
        "historical_unique_event_dates": int(s["event_date"].nunique()) if len(s) and "event_date" in s.columns else 0,
        "harvest_pdf_links": n_pdf,
    }
    return metrics


if __name__ == "__main__":
    rename_queue_study_status()
    harvest_miso_dpp_index()
    print(study_honesty_metrics())
