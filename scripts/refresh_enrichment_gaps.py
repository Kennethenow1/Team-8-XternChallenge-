#!/usr/bin/env python3
"""Fill DPP / HIFLD / MTEP / GDELT enrichment gaps and write coverage summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.enrichment.env import load_enrichment_env

load_enrichment_env()

import pandas as pd

from src.enrichment.build_crosswalks import build_geo_crosswalk
from src.enrichment.build_enriched_gold import _dpp_gold_eligible, build_enriched_panels
from src.enrichment.grid_pressure import populate_hifld_poi_context
from src.enrichment.ingest_gdelt import run_gdelt_ingest
from src.enrichment.ingest_miso_dpp import reextract_local_dpp_pdfs
from src.enrichment.ingest_mtep import run_mtep_harvest
from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
from src.enrichment.reports import build_all_reports


def _cov(df: pd.DataFrame, col: str) -> float | None:
    if df is None or df.empty or col not in df.columns:
        return None
    return float(df[col].notna().mean())


def main() -> int:
    ensure_enrichment_dirs()
    steps: dict[str, object] = {}

    print("=== 1/7 DPP local PDF re-extract ===")
    steps["dpp_reextract"] = reextract_local_dpp_pdfs()

    print("\n=== 2/7 Geo centroids (County Gazetteer) ===")
    geo = build_geo_crosswalk(enforce_gate=False)
    steps["geo_centroids"] = {
        "rows": int(len(geo)),
        "lat_coverage": _cov(geo, "latitude"),
        "fips_coverage": _cov(geo, "county_fips"),
    }

    print("\n=== 3/7 HIFLD transmission distances ===")
    assets = populate_hifld_poi_context()
    poi = (
        pd.read_parquet(SILVER_ENRICHMENT / "poi_grid_context.parquet")
        if (SILVER_ENRICHMENT / "poi_grid_context.parquet").exists()
        else pd.DataFrame()
    )
    steps["hifld"] = {
        "transmission_assets": int(len(assets)) if assets is not None else 0,
        "poi_grid_context": int(len(poi)),
        "distance_nonnull": _cov(poi, "distance_to_transmission_km"),
    }

    print("\n=== 4/7 MTEP harvest ===")
    mtep = run_mtep_harvest()
    steps["mtep"] = {
        "events": int(len(mtep)),
        "matched_project_keys": int(mtep["project_key"].notna().sum())
        if len(mtep) and "project_key" in mtep.columns
        else 0,
        "with_county_fips": int(mtep["county_fips"].notna().sum())
        if len(mtep) and "county_fips" in mtep.columns
        else 0,
    }

    print("\n=== 5/7 GDELT news ingest ===")
    news = run_gdelt_ingest()
    steps["gdelt"] = {
        "news_events": int(len(news)),
        "with_sentiment": int(news["sentiment_score"].notna().sum())
        if len(news) and "sentiment_score" in news.columns
        else 0,
    }

    print("\n=== 6/7 Enriched Gold ===")
    result = build_enriched_panels()
    build_all_reports(result["annual"])
    a = result["annual"]

    print("\n=== 7/7 gaps_fill_summary ===")
    dpp_path = SILVER_ENRICHMENT / "miso_dpp_events.parquet"
    dpp = pd.read_parquet(dpp_path) if dpp_path.exists() else pd.DataFrame()
    eligible = _dpp_gold_eligible(dpp) if len(dpp) else dpp

    summary = {
        "steps": steps,
        "dpp": {
            "n_silver_events": int(len(dpp)),
            "n_gold_eligible": int(len(eligible)),
            "pct_eligible_with_cost": _cov(eligible, "network_upgrade_cost"),
            "gold_network_upgrade_cost": _cov(a, "network_upgrade_cost"),
            "gold_study_delay_days": _cov(a, "study_delay_days"),
            "gold_restudy_count": _cov(a, "restudy_count"),
        },
        "hifld": {
            "n_transmission_assets": steps["hifld"]["transmission_assets"]
            if isinstance(steps.get("hifld"), dict)
            else 0,
            "gold_distance_to_transmission_km": _cov(a, "distance_to_transmission_km"),
        },
        "mtep": {
            "n_events": steps["mtep"]["events"] if isinstance(steps.get("mtep"), dict) else 0,
            "n_matched_project_keys": steps["mtep"]["matched_project_keys"]
            if isinstance(steps.get("mtep"), dict)
            else 0,
            "gold_nearby_mtep_upgrade_count": _cov(a, "nearby_mtep_upgrade_count"),
        },
        "gdelt": {
            "n_news_events": steps["gdelt"]["news_events"] if isinstance(steps.get("gdelt"), dict) else 0,
            "gold_news_count_90d": _cov(a, "news_count_90d"),
            "gold_news_sentiment_mean_90d": _cov(a, "news_sentiment_mean_90d"),
        },
    }
    ENRICHMENT_REPORTS.mkdir(parents=True, exist_ok=True)
    out = ENRICHMENT_REPORTS / "gaps_fill_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
