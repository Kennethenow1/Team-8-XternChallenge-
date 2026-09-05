"""Enrichment manifests, data dictionary, and coverage HTML report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.paths import GOLD_DIR
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    ensure_enrichment_dirs,
    load_enrichment_registry,
)
from src.enrichment.skeletons import TABLE_SCHEMAS


def build_source_manifest() -> pd.DataFrame:
    ensure_enrichment_dirs()
    rows = []
    for src in load_enrichment_registry():
        bronze = Path("data/bronze/enrichment") / src["bronze_subdir"]
        files = list(bronze.glob("*")) if bronze.exists() else []
        data_files = [f for f in files if not f.name.endswith(".meta.json") and f.name != "README.txt"]
        silver_hits = []
        for table in TABLE_SCHEMAS:
            p = SILVER_ENRICHMENT / f"{table}.parquet"
            if p.exists():
                df = pd.read_parquet(p)
                if len(df) and src["source_name"] and str(src["source_name"]).split("/")[0] in str(
                    df.get("source_name", pd.Series(dtype=str)).astype(str).head(1).tolist()
                ):
                    silver_hits.append(table)
        rows.append(
            {
                "source_id": src["source_id"],
                "source_name": src["source_name"],
                "category": src.get("category"),
                "grain": src.get("grain"),
                "status": src.get("status"),
                "source_url": src.get("source_url"),
                "bronze_files": len(data_files),
                "notes": src.get("notes"),
            }
        )
    # Also mark silver table row counts
    table_rows = []
    for table in TABLE_SCHEMAS:
        p = SILVER_ENRICHMENT / f"{table}.parquet"
        n = len(pd.read_parquet(p)) if p.exists() else 0
        table_rows.append({"silver_table": table, "row_count": n, "populated": n > 0})

    manifest = pd.DataFrame(rows)
    manifest.to_csv(ENRICHMENT_REPORTS / "enrichment_source_manifest.csv", index=False)
    pd.DataFrame(table_rows).to_csv(ENRICHMENT_REPORTS / "enrichment_silver_table_counts.csv", index=False)
    return manifest


def build_data_dictionary() -> pd.DataFrame:
    ensure_enrichment_dirs()
    rows = []
    for table, cols in TABLE_SCHEMAS.items():
        for c in cols:
            rows.append(
                {
                    "table": table,
                    "column": c,
                    "description": f"{table}.{c}",
                    "layer": "silver_enrichment",
                }
            )
    # Gold enriched features
    gold_feats = [
        "same_poi_project_count",
        "nearby_queue_mw",
        "same_group_prior_withdrawal_rate",
        "interest_rate_at_entry",
        "interest_rate_change_since_entry",
        "construction_cost_index_change_12m",
        "miso_mean_demand_mw",
        "miso_peak_demand_mw",
        "miso_demand_yoy_pct",
        "miso_generation_yoy_pct",
        "miso_net_interchange_mw",
        "fema_risk_score",
        "storm_events_12m",
        "storm_property_damage_12m",
        "extreme_weather_days_12m",
        "energy_community_eligible",
        "developer_active_project_count",
        "developer_total_active_mw",
        "developer_prior_completion_rate",
        "developer_prior_withdrawal_rate",
        "capacity_reduction_pct",
    ]
    for c in gold_feats:
        rows.append(
            {
                "table": "withdrawal_panel_enriched",
                "column": c,
                "description": f"PIT enrichment feature: {c}",
                "layer": "gold",
            }
        )
    dd = pd.DataFrame(rows)
    dd.to_csv(ENRICHMENT_REPORTS / "enrichment_data_dictionary.csv", index=False)
    return dd


def build_coverage_report(enriched: pd.DataFrame | None = None) -> Path:
    ensure_enrichment_dirs()
    if enriched is None:
        path = GOLD_DIR / "withdrawal_panel_enriched.parquet"
        enriched = pd.read_parquet(path) if path.exists() else pd.DataFrame()

    feature_cols = [
        c
        for c in enriched.columns
        if c
        in {
            "same_poi_project_count",
            "nearby_queue_mw",
            "same_group_prior_withdrawal_rate",
            "interest_rate_at_entry",
            "interest_rate_change_since_entry",
            "construction_cost_index_change_12m",
            "miso_mean_demand_mw",
            "miso_peak_demand_mw",
            "miso_demand_yoy_pct",
            "miso_generation_yoy_pct",
            "miso_net_interchange_mw",
            "fema_risk_score",
            "storm_events_12m",
            "storm_property_damage_12m",
            "extreme_weather_days_12m",
            "energy_community_eligible",
            "developer_active_project_count",
            "developer_total_active_mw",
            "developer_prior_completion_rate",
            "developer_prior_withdrawal_rate",
            "capacity_reduction_pct",
            "county_fips",
            "rural_flag",
            "population",
            "population_yoy_pct",
            "population_change_since_2020",
            "pep_vintage",
        }
    ]

    coverage_rows = []
    if len(enriched) and "observation_date" in enriched.columns:
        enriched = enriched.copy()
        enriched["obs_year"] = pd.to_datetime(enriched["observation_date"]).dt.year
        for year, g in enriched.groupby("obs_year"):
            for c in feature_cols:
                coverage_rows.append(
                    {
                        "year": int(year),
                        "feature": c,
                        "n_rows": len(g),
                        "n_nonnull": int(g[c].notna().sum()),
                        "coverage_pct": round(100.0 * g[c].notna().mean(), 2),
                    }
                )
        # by project overall
        for c in feature_cols:
            coverage_rows.append(
                {
                    "year": "ALL",
                    "feature": c,
                    "n_rows": len(enriched),
                    "n_nonnull": int(enriched[c].notna().sum()),
                    "coverage_pct": round(100.0 * enriched[c].notna().mean(), 2),
                }
            )

    cov = pd.DataFrame(coverage_rows)
    cov.to_csv(ENRICHMENT_REPORTS / "enrichment_coverage_by_feature.csv", index=False)

    manifest = pd.read_csv(ENRICHMENT_REPORTS / "enrichment_source_manifest.csv")
    table_counts = pd.read_csv(ENRICHMENT_REPORTS / "enrichment_silver_table_counts.csv")

    # Simple HTML
    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Enrichment Coverage Report</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:2rem}table{border-collapse:collapse}",
        "th,td{border:1px solid #ccc;padding:4px 8px;font-size:13px}th{background:#f4f4f4}</style>",
        "</head><body>",
        "<h1>Enrichment Coverage Report</h1>",
        "<p>Point-in-time enrichment feature store — coverage by source and feature. No model metrics.</p>",
        "<h2>Sources</h2>",
        manifest.to_html(index=False),
        "<h2>Silver table row counts</h2>",
        table_counts.to_html(index=False),
        "<h2>Feature coverage on withdrawal_panel_enriched</h2>",
    ]
    if len(cov):
        pivot = cov[cov["year"] == "ALL"][["feature", "n_nonnull", "n_rows", "coverage_pct"]]
        html.append(pivot.to_html(index=False))
        html.append("<h3>By year (sample)</h3>")
        html.append(cov[cov["year"] != "ALL"].head(80).to_html(index=False))
    else:
        html.append("<p>No enriched panel found.</p>")
    html.append("</body></html>")

    out = ENRICHMENT_REPORTS / "enrichment_coverage_report.html"
    out.write_text("\n".join(html), encoding="utf-8")
    print(f"Wrote {out}")
    return out


def build_all_reports(enriched: pd.DataFrame | None = None) -> None:
    build_source_manifest()
    build_data_dictionary()
    build_coverage_report(enriched)
    # Ensure match review exists
    review = SILVER_ENRICHMENT.parent / "crosswalks" / "enrichment_match_review.csv"
    if review.exists():
        import shutil

        shutil.copy(review, ENRICHMENT_REPORTS / "enrichment_match_review.csv")


if __name__ == "__main__":
    build_all_reports()
