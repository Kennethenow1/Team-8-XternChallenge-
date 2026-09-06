# Silver — clean, join-ready tables

**What Silver is:** standardized schemas. Queue projects, point-in-time **snapshots**, outcomes, crosswalks, and **enrichment** tables that carry `available_date` (and related metadata) so Gold can join without leakage.

**What Silver is not:** the final labeled modeling matrix (that is Gold). Enrichment here is still “feature inventory,” not yet merged onto every training row.

## Layout

| Path | Function | Helps prediction by… |
|------|----------|----------------------|
| `projects/` | Berkeley + MISO project master | Identity, MW, tech, developer, location |
| `snapshots/` | PIT queue observations over time | Age, status, capacity at date *t* |
| `outcomes/` | Withdrawal / completion events | Building labels later in Gold |
| `crosswalks/` | project → FIPS, developer ID, EIA plant | Linking geography & sponsors |
| `enrichment/` | Typed external feature tables | Cost, grid, macro, news, risk, … |
| `external/` | **Deprecated** empty stubs | Ignore — superseded by `enrichment/` |

## Enrichment tables (`enrichment/`)

| Table | From (bronze / logic) | Prediction role |
|-------|----------------------|-----------------|
| `miso_dpp_events` / `study_events` | DPP PDFs | Study cost shock, delays, restudies |
| `queue_study_status` | Queue fields | Current study phase |
| `poi_grid_context` / `transmission_assets` | HIFLD + queue POI | Interconnection friction |
| `mtep_project_events` | MTEP Excel | Nearby upgrade / $ investment |
| `news_events` | GDELT | Opposition / attention / sentiment |
| `market_zone_month` / `miso_zone_month` | FRED + EIA-930 | Rates, demand, interchange |
| `county_year` / `county_month` | Census + FEMA (+ related) | Population, rurality, risk |
| `weather_county_month` | NOAA | Storm / extreme weather |
| `policy_state_date` | Energy communities | IRA siting incentive |
| `developer_quarter` | Queue history | Sponsor withdrawal / completion rates |
| `eia_generator_month` | EIA-860 | Plant context (weak name match) |
| `site_geospatial_features` | Geo joins | Site-level spatial context |
| `permit_events` / others | Stubs or partial | Reserved for later fills |

**Rule:** rows meant for PIT joins include `available_date` (and usually `effective_date`, `source_*`, match metadata). Gold must use `available_date ≤ observation_date`.

Next layer: [`../gold/README.md`](../gold/README.md). Full catalog: [`../../docs/data_catalog.md`](../../docs/data_catalog.md).
