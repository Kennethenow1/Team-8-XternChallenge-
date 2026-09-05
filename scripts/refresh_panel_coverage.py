#!/usr/bin/env python3
"""Refresh county/population/FEMA/EC + DPP-filtered Gold panel; write solidify summary."""

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

from src.enrichment.build_enriched_gold import _dpp_gold_eligible, build_enriched_panels
from src.enrichment.populate import populate_county_year_fema_acs, populate_policy_energy_communities
from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs
from src.enrichment.reports import build_all_reports


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
