#!/usr/bin/env python3
"""
Full enrichment populate → enriched Gold refresh.

Order:
  skeletons(missing) → geo gate → preserve DPP / queue_study_status →
  EIA → grid → county joins → FRED/weather/developer → enriched Gold → reports

Does NOT rebuild Berkeley/MISO core queue tables. Does NOT train models.
Does NOT wipe historical miso_dpp_events.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.enrichment.env import load_enrichment_env

load_enrichment_env()

from src.enrichment.build_crosswalks import build_all_crosswalks
from src.enrichment.build_enriched_gold import build_enriched_panels
from src.enrichment.grid_pressure import populate_grid_pressure
from src.enrichment.ingest_eia860 import populate_eia860
from src.enrichment.populate import populate_all
from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
from src.enrichment.reports import build_all_reports
from src.enrichment.skeletons import write_all_skeleton_tables
from src.enrichment.study_tables import harvest_miso_dpp_index, rename_queue_study_status, study_honesty_metrics


def main() -> int:
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
        import pandas as pd

        n = len(pd.read_parquet(dpp))
        if n == 0:
            print("WARNING: miso_dpp_events empty — run scripts/run_miso_dpp_ingest.py first")
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

    import pandas as pd

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
    print("\nEnrichment populate + Gold refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
