# Data catalog — sources, paths, prediction roles

Index of datasets: **where they come from**, **where they live**, and **how they help predict interconnection withdrawal**.

Folder rules: [data_layout.md](data_layout.md). Layer intros:

- [`data/README.md`](../data/README.md) — overview
- [`data/intake/README.md`](../data/intake/README.md) — raw downloads
- [`data/bronze/README.md`](../data/bronze/README.md)
- [`data/silver/README.md`](../data/silver/README.md)
- [`data/gold/README.md`](../data/gold/README.md)

## Bronze → Silver → Gold

| Layer | Meaning | Safe to model on? |
|-------|---------|-------------------|
| **Intake** | Hand-dropped source files | No |
| **Bronze** | Byte-stable copies (+ hashes) | No — audit trail |
| **Silver** | Clean tables; enrichment has `available_date` | Prefer Gold |
| **Gold** | Labeled / scoring panels | **Yes** |

## Core queue

| Dataset | From | Path flow | Gold use | Prediction role |
|---------|------|-----------|----------|-----------------|
| Berkeley / LBNL IX queue | Workbooks in `data/intake/` | → `bronze/berkeley` → `silver/projects` | Snapshots → annual / survival | Project fundamentals |
| MISO current queue | CSV in `data/intake/` | → `bronze/miso` → `silver/projects` | Current scoring | Live queue state |
| Snapshots | Derived | `silver/snapshots` | Annual & survival | PIT status / MW / age |
| Outcomes | Derived | `silver/outcomes` | Labels | Withdraw / complete events |

## Enrichment by prediction role

### Study / cost shock

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `miso_dpp_events`, `study_events` | MISO DPP GI PDFs | Network upgrade $, delays, restudies |
| `queue_study_status` | Queue fields | Current study phase |

### Grid / interconnection friction

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `poi_grid_context`, `transmission_assets` | HIFLD | Distance to line, voltage |
| `mtep_project_events` | MISO MTEP Appendix A | Nearby upgrade count / $ |
| Queue-derived POI / state crowding | Snapshots | Same-POI / state congestion |

### Developer quality

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `developer_quarter` | Queue history | Prior withdrawal & completion rates |

### Local market, risk, policy

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `county_year` (+ related) | Census, FEMA NRI | Population, rurality, disaster risk |
| `weather_county_month` | NOAA Storm Events | Extreme weather |
| `policy_state_date` | Treasury energy communities | IRA bonus-credit eligibility |
| Crosswalk `geo_crosswalk` | Census gazetteer / FIPS | County key + lat/lon |

### Macro / system stress

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `market_zone_month` | FRED + EIA-930 | Rates, PPI, MISO demand/gen |

### News / opposition

| Silver table | Source | Helps by… |
|--------------|--------|-----------|
| `news_events` | GDELT GKG (bounded) | News volume, sentiment |

### Sparse / stub

| Silver table | Source | Notes |
|--------------|--------|-------|
| `eia_generator_month` | EIA-860 | Weak exact name match |
| `permit_events`, LMP, SEC, … | Stubs | Schema reserved |

## Gold products

| Path | Grain | Label? | Role |
|------|-------|--------|------|
| `data/gold/annual_withdrawal_training/` | project × year | `withdraw_next_12m` | Base classification |
| `data/gold/survival_training/` | interval rows | event indicators | Survival |
| `data/gold/current_miso_scoring/` | active projects | **no** | Score candidates |
| `data/gold/withdrawal_panel_enriched.*` | project × year + enrichment | yes | Full research panel |
| `data/gold/current_miso_scoring_enriched.*` | active + enrichment | no | Live scoring |
| `data/gold/modeling/model_ready_train.*` | train engineered | yes | **Preferred train matrix** |

## Quality reports (not datasets)

| Path | Purpose |
|------|---------|
| `data/quality_reports/enrichment/` | Coverage, harvest summaries |
| `data/quality_reports/modeling/` | Corr preview, engineering notes |

Applied transforms: `feature_engineering_notes.md`. Pre-engineering only: `collapse_recommendations.md`.
