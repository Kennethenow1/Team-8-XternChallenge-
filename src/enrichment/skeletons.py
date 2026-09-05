"""Empty typed Silver enrichment skeletons for registered_empty sources."""

from __future__ import annotations

import pandas as pd

from src.enrichment.registry import empty_enrichment_frame, ensure_enrichment_dirs, write_silver_table

# Extra columns per table beyond mandatory metadata
TABLE_SCHEMAS: dict[str, list[str]] = {
    "study_events": [
        "project_key",
        "study_cycle",
        "study_group",
        "study_phase",
        "upgrade_cost_usd",
        "upgrade_cost_per_mw",
        "capacity_mw",
        "capacity_reduction_pct",
        "restudy_flag",
        "report_date",
    ],
    "transmission_assets": [
        "upgrade_id",
        "poi_key",
        "transmission_owner",
        "upgrade_completion_year",
        "investment_usd",
        "voltage_kv",
        "distance_to_transmission_km",
    ],
    "market_zone_month": [
        "miso_zone",
        "year_month",
        "miso_mean_demand_mw",
        "miso_peak_demand_mw",
        "miso_demand_yoy_pct",
        "miso_generation_yoy_pct",
        "miso_net_interchange_mw",
        "demand_mw_mean",
        "demand_mw_peak",
        "net_interchange_mw",
        "local_demand_growth",
        "renewable_share",
        "interest_rate_10y",
        "ppi_construction",
        "local_congestion_mean",
        "local_congestion_volatility",
    ],
    "generator_status_events": [
        "eia_plant_id",
        "project_key",
        "status",
        "operating_date",
        "capacity_mw",
        "technology",
        "event_type",
    ],
    "developer_quarter": [
        "developer_id",
        "year_quarter",
        "developer_active_project_count",
        "developer_total_active_mw",
        "developer_prior_completion_rate",
        "developer_prior_withdrawal_rate",
        "developer_financing_event_180d",
        "developer_distress_event_180d",
    ],
    "permit_events": [
        "project_key",
        "facility_name",
        "permit_type",
        "event_type",
        "milestone",
        "missed_deadline_flag",
    ],
    "news_events": [
        "news_event_id",
        "project_id",
        "developer_id",
        "published_at",
        "source_domain",
        "article_title",
        "article_url",
        "event_type",
        "sentiment_score",
        "relevance_score",
        "location_match_score",
        "entity_match_score",
        "duplicate_group_id",
        "extraction_confidence",
    ],
    "county_month": [
        "county_fips",
        "year_month",
        "construction_employment",
        "construction_wage",
        "storm_events",
        "storm_property_damage",
        "extreme_weather_days",
    ],
    "county_year": [
        "county_fips",
        "year",
        "population",
        "median_income",
        "rural_flag",
        "fema_risk_score",
        "county_gdp",
        "county_gdp_growth",
        "energy_community_eligible",
    ],
    "weather_county_month": [
        "county_fips",
        "year_month",
        "temp_mean",
        "precip_mm",
        "snow_days",
        "extreme_weather_days",
        "storm_events",
        "storm_property_damage",
    ],
    "site_geospatial_features": [
        "project_key",
        "solar_resource_percentile",
        "wind_resource_percentile",
        "wetlands_overlap_pct",
        "distance_to_wetlands_km",
        "drought_months_12m",
        "distance_to_transmission_km",
    ],
    "policy_state_date": [
        "state_code",
        "county_fips",
        "policy_type",
        "energy_community_eligible",
        "policy_id",
    ],
}


def write_empty_table(name: str) -> pd.DataFrame:
    ensure_enrichment_dirs()
    extras = TABLE_SCHEMAS.get(name, [])
    df = empty_enrichment_frame(extras)
    # Ensure date cols are datetime-friendly empty
    write_silver_table(name, df)
    return df


def write_all_skeleton_tables(only_if_missing: bool = False) -> list[str]:
    """Write empty schemas for all enrichment tables (may be overwritten by populate)."""
    from src.enrichment.registry import SILVER_ENRICHMENT

    written = []
    for name in TABLE_SCHEMAS:
        path = SILVER_ENRICHMENT / f"{name}.parquet"
        if only_if_missing and path.exists():
            continue
        write_empty_table(name)
        written.append(name)
    return written


if __name__ == "__main__":
    print(write_all_skeleton_tables())
