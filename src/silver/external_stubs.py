"""External dataset schema stubs for future point-in-time joins."""

from __future__ import annotations

import json

import pandas as pd

from src.common.paths import SILVER_DIR, ensure_layer_dirs

# Dataset -> recommended grain (from plan §19)
EXTERNAL_DATASETS = {
    "weather": {
        "grain": "county × day/month",
        "geographic_key": "county_fips",
        "columns": [
            "county_fips",
            "event_date",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "event_type",
            "severity_flag",
        ],
    },
    "economic": {
        "grain": "county × quarter/year",
        "geographic_key": "county_fips",
        "columns": [
            "county_fips",
            "period_start",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "employment_level",
            "employment_growth_yoy",
        ],
    },
    "electricity_demand": {
        "grain": "MISO region/zone × hour/day",
        "geographic_key": "miso_zone",
        "columns": [
            "miso_zone",
            "timestamp",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "load_mw",
        ],
    },
    "market_prices": {
        "grain": "pricing node × hour",
        "geographic_key": "pricing_node",
        "columns": [
            "pricing_node",
            "timestamp",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "lmp",
        ],
    },
    "transmission_upgrades": {
        "grain": "upgrade/POI × observation date",
        "geographic_key": "poi_key",
        "columns": [
            "poi_key",
            "upgrade_id",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "status",
        ],
    },
    "permits": {
        "grain": "project/facility × event date",
        "geographic_key": "project_key",
        "columns": [
            "project_key",
            "event_date",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "permit_type",
            "event_type",
        ],
    },
    "news": {
        "grain": "project/developer × publication date",
        "geographic_key": "project_key",
        "columns": [
            "project_key",
            "developer",
            "publication_date",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "sentiment",
        ],
    },
    "policy": {
        "grain": "jurisdiction × effective date",
        "geographic_key": "state_code",
        "columns": [
            "state_code",
            "policy_id",
            "effective_at",
            "published_at",
            "available_at",
            "source",
            "policy_type",
        ],
    },
}

PIT_JOIN_RULE = (
    "Point-in-time join: external.available_at <= project.observation_date; "
    "then select most recent eligible record or compute trailing windows. "
    "Never join on calendar year alone if that leaks future months into earlier predictions."
)


def write_external_stubs() -> None:
    ensure_layer_dirs()
    ext_dir = SILVER_DIR / "external"
    ext_dir.mkdir(parents=True, exist_ok=True)

    catalog = {"pit_join_rule": PIT_JOIN_RULE, "datasets": {}}
    for name, meta in EXTERNAL_DATASETS.items():
        empty = pd.DataFrame({c: pd.Series(dtype="object") for c in meta["columns"]})
        empty.to_parquet(ext_dir / f"{name}.parquet", index=False)
        schema_path = ext_dir / f"{name}_schema.json"
        schema_path.write_text(
            json.dumps(
                {
                    "dataset": name,
                    "grain": meta["grain"],
                    "geographic_key": meta["geographic_key"],
                    "columns": meta["columns"],
                    "pit_join_rule": PIT_JOIN_RULE,
                    "example_features": _example_features(name),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        catalog["datasets"][name] = {
            "grain": meta["grain"],
            "geographic_key": meta["geographic_key"],
            "parquet": f"data/silver/external/{name}.parquet",
            "schema": f"data/silver/external/{name}_schema.json",
        }

    (ext_dir / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote {len(EXTERNAL_DATASETS)} external stubs to {ext_dir}")


def _example_features(name: str) -> list[str]:
    return {
        "weather": ["weather_events_prior_12m"],
        "economic": ["county_employment_growth_prior_year"],
        "electricity_demand": ["mean_load_prior_90d"],
        "market_prices": ["mean_lmp_prior_90d", "price_volatility_prior_90d"],
        "transmission_upgrades": ["upgrades_available_prior_obs"],
        "permits": ["permit_events_prior_12m"],
        "news": ["negative_project_news_prior_90d"],
        "policy": ["policy_changes_prior_12m"],
    }.get(name, [])


if __name__ == "__main__":
    write_external_stubs()
