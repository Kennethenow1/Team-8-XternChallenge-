#!/usr/bin/env python3
"""Canonical enrichment CLI.

Subcommands:
  skeleton  — skeletons / crosswalks / populate / enriched Gold (light path)
  sprint    — geo gate + EIA + grid + populate + Gold (main enrichment refresh)
  gaps      — DPP / HIFLD / MTEP / GDELT fill + Gold
  panel     — county / FEMA / energy-community refresh + Gold
  dpp       — DPP PDF acquire/extract only (does not merge Gold)

Prefer:  python scripts/run_enrichment.py <subcommand>
Legacy script names remain as thin wrappers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.enrichment.env import load_enrichment_env

load_enrichment_env()


def _cmd_skeleton() -> int:
    from src.enrichment.build_crosswalks import build_all_crosswalks
    from src.enrichment.build_enriched_gold import build_enriched_panels
    from src.enrichment.populate import populate_all
    from src.enrichment.registry import ensure_enrichment_dirs
    from src.enrichment.reports import build_all_reports
    from src.enrichment.skeletons import write_all_skeleton_tables

    ensure_enrichment_dirs()

    print("=== E0/E2: Write typed Silver skeletons (missing only) ===")
    write_all_skeleton_tables(only_if_missing=True)

    print("\n=== E0: Geo / developer / EIA crosswalks ===")
    build_all_crosswalks()

    print("\n=== E1: Populate open + queue-derived sources ===")
    populate_all(run_deferred_county_joins=True)

    print("\n=== E2: Re-assert empty skeletons for tables still empty ===")
    write_all_skeleton_tables(only_if_missing=True)

    print("\n=== E3: Enriched Gold panels ===")
    result = build_enriched_panels()

    print("\n=== E3: Manifests / coverage / dictionary ===")
    build_all_reports(result["annual"])

    dep = REPO_ROOT / "data" / "silver" / "external" / "DEPRECATED.txt"
    dep.parent.mkdir(parents=True, exist_ok=True)
    dep.write_text(
        "Superseded by data/silver/enrichment/. Kept for backward reference only.\n",
        encoding="utf-8",
    )

    print("\nEnrichment skeleton path complete.")
    return 0


def _cmd_sprint() -> int:
    import pandas as pd

    from src.enrichment.build_crosswalks import build_all_crosswalks
    from src.enrichment.build_enriched_gold import build_enriched_panels
    from src.enrichment.grid_pressure import populate_grid_pressure
    from src.enrichment.ingest_eia860 import populate_eia860
    from src.enrichment.populate import populate_all
    from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
    from src.enrichment.reports import build_all_reports
    from src.enrichment.skeletons import write_all_skeleton_tables
    from src.enrichment.study_tables import harvest_miso_dpp_index, rename_queue_study_status, study_honesty_metrics

    ensure_enrichment_dirs()
    write_all_skeleton_tables(only_if_missing=True)

    print("=== 1. Geo gate (FIPS >= 90%) ===")
    build_all_crosswalks(enforce_geo_gate=True)

    print("\n=== 2. Study tables (preserve DPP history) ===")
    rename_queue_study_status()
    harvest_miso_dpp_index()
    honesty = study_honesty_metrics()
    print("study honesty:", honesty)
    (ENRICHMENT_REPORTS / "study_honesty_metrics.json").write_text(
        json.dumps(honesty, indent=2), encoding="utf-8"
    )
    dpp = SILVER_ENRICHMENT / "miso_dpp_events.parquet"
    if dpp.exists():
        n = len(pd.read_parquet(dpp))
        if n == 0:
            print("WARNING: miso_dpp_events empty — run: python scripts/run_enrichment.py dpp")
        else:
            print(f"DPP events ready for Gold: {n}")

    print("\n=== 3. EIA-860 / 860M ===")
    eia_stats = populate_eia860()
    print("eia:", eia_stats)

    print("\n=== 4. Grid pressure ===")
    populate_grid_pressure()

    print("\n=== 5. Populate open sources + county joins ===")
    populate_all(run_deferred_county_joins=True)

    print("\n=== 6. Enriched Gold + coverage ===")
    result = build_enriched_panels()
    build_all_reports(result["annual"])

    a = result["annual"]

    def cov(col: str) -> float | None:
        return float(a[col].notna().mean()) if col in a.columns else None

    summary = {
        "rows_annual": len(a),
        "geo_fips_on_panel": cov("county_fips"),
        "storm_events_12m": cov("storm_events_12m"),
        "population": cov("population"),
        "interest_rate_at_entry": cov("interest_rate_at_entry"),
        "same_poi_project_count": cov("same_poi_project_count"),
        "dpp_event_count_to_date": cov("dpp_event_count_to_date"),
        "study_delay_days": cov("study_delay_days"),
        "restudy_count": cov("restudy_count"),
        "network_upgrade_cost": cov("network_upgrade_cost"),
        "miso_mean_demand_mw": cov("miso_mean_demand_mw"),
        "study_honesty": honesty,
        "eia": eia_stats,
        "gold_merged_dpp": True,
    }
    (ENRICHMENT_REPORTS / "dataset_refresh_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (ENRICHMENT_REPORTS / "sprint_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nDataset refresh summary:", json.dumps(summary, indent=2))
    print("\nEnrichment sprint complete.")
    return 0


def _cmd_gaps() -> int:
    import pandas as pd

    from src.enrichment.build_crosswalks import build_geo_crosswalk
    from src.enrichment.build_enriched_gold import _dpp_gold_eligible, build_enriched_panels
    from src.enrichment.grid_pressure import populate_hifld_poi_context
    from src.enrichment.ingest_gdelt import run_gdelt_ingest
    from src.enrichment.ingest_miso_dpp import reextract_local_dpp_pdfs
    from src.enrichment.ingest_mtep import run_mtep_harvest
    from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
    from src.enrichment.reports import build_all_reports

    def cov(df: pd.DataFrame, col: str) -> float | None:
        if df is None or df.empty or col not in df.columns:
            return None
        return float(df[col].notna().mean())

    ensure_enrichment_dirs()
    steps: dict[str, object] = {}

    print("=== 1/7 DPP local PDF re-extract ===")
    steps["dpp_reextract"] = reextract_local_dpp_pdfs()

    print("\n=== 2/7 Geo centroids (County Gazetteer) ===")
    geo = build_geo_crosswalk(enforce_gate=False)
    steps["geo_centroids"] = {
        "rows": int(len(geo)),
        "lat_coverage": cov(geo, "latitude"),
        "fips_coverage": cov(geo, "county_fips"),
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
        "distance_nonnull": cov(poi, "distance_to_transmission_km"),
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
            "pct_eligible_with_cost": cov(eligible, "network_upgrade_cost"),
            "gold_network_upgrade_cost": cov(a, "network_upgrade_cost"),
            "gold_study_delay_days": cov(a, "study_delay_days"),
            "gold_restudy_count": cov(a, "restudy_count"),
        },
        "hifld": {
            "n_transmission_assets": steps["hifld"]["transmission_assets"]
            if isinstance(steps.get("hifld"), dict)
            else 0,
            "gold_distance_to_transmission_km": cov(a, "distance_to_transmission_km"),
        },
        "mtep": {
            "n_events": steps["mtep"]["events"] if isinstance(steps.get("mtep"), dict) else 0,
            "n_matched_project_keys": steps["mtep"]["matched_project_keys"]
            if isinstance(steps.get("mtep"), dict)
            else 0,
            "gold_nearby_mtep_upgrade_count": cov(a, "nearby_mtep_upgrade_count"),
        },
        "gdelt": {
            "n_news_events": steps["gdelt"]["news_events"] if isinstance(steps.get("gdelt"), dict) else 0,
            "gold_news_count_90d": cov(a, "news_count_90d"),
            "gold_news_sentiment_mean_90d": cov(a, "news_sentiment_mean_90d"),
        },
    }
    ENRICHMENT_REPORTS.mkdir(parents=True, exist_ok=True)
    out = ENRICHMENT_REPORTS / "gaps_fill_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {out}")
    return 0


def _cmd_panel() -> int:
    import pandas as pd

    from src.enrichment.build_enriched_gold import _dpp_gold_eligible, build_enriched_panels
    from src.enrichment.populate import populate_county_year_fema_acs, populate_policy_energy_communities
    from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
    from src.enrichment.reports import build_all_reports

    ensure_enrichment_dirs()
    dpp_path = SILVER_ENRICHMENT / "miso_dpp_events.parquet"
    dpp_before = len(pd.read_parquet(dpp_path)) if dpp_path.exists() else 0

    print("=== County year: multi-year popest + FEMA NRI ===")
    populate_county_year_fema_acs()

    print("\n=== Energy communities ===")
    populate_policy_energy_communities()

    print("\n=== Enriched Gold (DPP filtered at join) ===")
    result = build_enriched_panels()
    build_all_reports(result["annual"])

    a = result["annual"]
    dpp_after = len(pd.read_parquet(dpp_path)) if dpp_path.exists() else 0
    dpp = pd.read_parquet(dpp_path) if dpp_path.exists() else pd.DataFrame()
    eligible = _dpp_gold_eligible(dpp) if len(dpp) else dpp

    def cov(col: str) -> float | None:
        return float(a[col].notna().mean()) if col in a.columns else None

    pop_by_year = {}
    if "observation_date" in a.columns and "population" in a.columns:
        tmp = a.copy()
        tmp["_y"] = pd.to_datetime(tmp["observation_date"]).dt.year
        for y, g in tmp.groupby("_y"):
            pop_by_year[str(int(y))] = float(g["population"].notna().mean())

    summary = {
        "population": cov("population"),
        "population_by_observation_year": pop_by_year,
        "fema_risk_score": cov("fema_risk_score"),
        "energy_community_eligible": cov("energy_community_eligible"),
        "n_silver_dpp_events": dpp_after,
        "n_silver_dpp_events_before": dpp_before,
        "dpp_row_count_unchanged": dpp_before == dpp_after,
        "n_gold_eligible_dpp_events": int(len(eligible)),
        "dpp_event_count_to_date": cov("dpp_event_count_to_date"),
        "study_delay_days": cov("study_delay_days"),
        "restudy_count": cov("restudy_count"),
        "network_upgrade_cost": cov("network_upgrade_cost"),
        "population_gate_pass": (cov("population") or 0) >= 0.80,
    }
    ENRICHMENT_REPORTS.mkdir(parents=True, exist_ok=True)
    out = ENRICHMENT_REPORTS / "panel_solidify_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out}")
    return 0


def _cmd_dpp(*, skip_playwright: bool = False) -> int:
    from src.enrichment.ingest_miso_dpp import run_miso_dpp_ingest

    run_miso_dpp_ingest(skip_playwright=skip_playwright)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_enrichment.py",
        description="Canonical enrichment CLI (Silver populate + enriched Gold).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("skeleton", help="Skeletons, crosswalks, populate, enriched Gold")
    sub.add_parser("sprint", help="Full sprint: geo, EIA, grid, populate, Gold")
    sub.add_parser("gaps", help="Fill DPP/HIFLD/MTEP/GDELT gaps and rewrite Gold")
    sub.add_parser("panel", help="Refresh county/FEMA/EC coverage and rewrite Gold")
    dpp = sub.add_parser("dpp", help="Acquire/extract MISO DPP PDFs (no Gold merge)")
    dpp.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip Playwright network capture (still uses Optics API index).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "skeleton":
        return _cmd_skeleton()
    if args.command == "sprint":
        return _cmd_sprint()
    if args.command == "gaps":
        return _cmd_gaps()
    if args.command == "panel":
        return _cmd_panel()
    if args.command == "dpp":
        return _cmd_dpp(skip_playwright=args.skip_playwright)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
