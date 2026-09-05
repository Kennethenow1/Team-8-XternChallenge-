# Team 8 — Point-in-Time MISO Interconnection Queue Database

Build a **point-in-time (PIT)** feature store for modeling whether a MISO generator interconnection queue project **withdraws in the next 12 months**.

Each enriched training row means:

> Everything that could legitimately be known about project \(i\) on observation date \(t\) — queue state, study costs, grid context, local risk, news — without using information published after \(t\). Did it withdraw in the following year?

No model training lives in this repo yet. The product is the database and enrichment joins.

---

## How the database is organized

```
Data/                         # Original downloads (staging; not edited by pipeline)
data/
  bronze/                     # Immutable source copies (hash-checked)
    enrichment/               # External feeds (DPP PDFs, HIFLD, MTEP, GDELT, Census, …)
  silver/
    projects/                 # Standardized Berkeley + MISO project tables
    snapshots/                # Point-in-time queue observations
    crosswalks/               # project→county FIPS, developer, EIA plant keys
    enrichment/               # Typed PIT feature tables (join keys + available_date)
  gold/
    annual_withdrawal_training/   # Labels + base covariates
    survival_training/
    current_miso_scoring/         # Active projects, no future labels
    withdrawal_panel_enriched.*   # ★ Main modeling table (queue + enrichment)
    current_miso_scoring_enriched.*
  quality_reports/enrichment/ # Coverage, leakage audit, harvest summaries
configs/
  source_registry.yaml        # Core queue sources
  enrichment_registry.yaml    # External feature sources + status
scripts/                      # run_pipeline, enrichment sprint, gaps refresh
src/                          # Ingest, standardize, enrich, PIT joins
```

| Layer | Rule |
|-------|------|
| **Bronze** | Raw copies only. Never mutate in place. |
| **Silver** | Clean schemas; enrichment rows carry `effective_date`, `available_date`, `source_*`, match metadata. |
| **Gold** | Modeling tables. Labels only on historical training sets. External features join with `available_date ≤ observation_date`. |
| **Missing values** | Stay null. Never invent DPP report dates or zero-fill “no data” as zero risk. |

---

## Current database state (snapshot)

Approximate sizes after the enrichment gaps fill (see `data/quality_reports/enrichment/gaps_fill_summary.json`):

### Core queue

| Table | Scale | Role toward the goal |
|-------|------:|----------------------|
| Berkeley projects | ~24k | Historical IX queue (capacity, tech, status, developer, location) |
| MISO projects | ~3.8k | Current MISO queue |
| Project snapshots | ~28k | PIT status/capacity by date — basis for annual panels |
| Annual training Gold | ~9.8k × 31 | `withdraw_next_12m` label + queue covariates |
| Current scoring Gold | ~1.0k | Active MISO projects to score (no labels) |
| **Enriched panel** | **~9.8k × ~124** | Training table + all usable external features |

### Enrichment on the enriched Gold panel

| Feature family | Gold coverage (approx.) | What it contributes |
|----------------|------------------------:|---------------------|
| County FIPS / centroids | ~97% | Geography for all county joins |
| Population / FEMA risk | ~98% | Local demand / disaster exposure |
| Energy community (IRA) | ~42% | Policy / financing incentive signal |
| Interest rates + MISO demand | ~100% | Macro cost of capital + BA-wide load pressure |
| Same-POI / developer history | ~100% | Queue crowding and sponsor track record |
| Distance to transmission (HIFLD) | ~98% | Grid interconnection friction proxy |
| Nearby MTEP upgrades | ~99% | Transmission investment context (state-level) |
| News count / sentiment (GDELT) | ~99% | Local opposition / energy news tone |
| DPP upgrade cost | ~10% | Study-driven cost shock (only where PDFs exist) |
| Study delay / restudy | ~8% | Process friction (needs ≥2 dated eligible events) |

Thin DPP coverage is **honest**: most projects never appear in harvested public DPP PDFs. Among Gold-eligible DPP events (~1.1k), cost is present on ~76%.

---

## What each dataset provides (toward withdrawal risk)

### Always-on / high coverage

| Source | Silver home | Brings into the model |
|--------|-------------|------------------------|
| **Berkeley + MISO queues** | `projects/`, `snapshots/` | Age in queue, MW, technology, hybrid flags, study phase, POI crowding |
| **Census county FIPS + gazetteer** | `crosswalks/geo_crosswalk` | County key + lat/lon for spatial joins |
| **Developer crosswalk** | `crosswalks/developer_crosswalk` | Stable sponsor ID |
| **Census population / ACS proxies** | `county_year` | Market size / rurality |
| **FEMA National Risk Index** | `county_year` | County disaster risk score |
| **Treasury / DOE energy communities** | `policy_state_date` | Bonus-credit eligibility |
| **FRED (DGS10, PPI)** | `market_zone_month` | Financing and construction cost environment |
| **EIA-930 MISO BA** | `market_zone_month` | System demand, generation, interchange |
| **NOAA Storm Events** | `weather_county_month` | Extreme weather pressure |
| **Queue-derived developer history** | `developer_quarter` | Prior withdrawal / completion rates |
| **HIFLD transmission lines** | `transmission_assets`, `poi_grid_context` | `distance_to_transmission_km`, nearby voltage |
| **MISO MTEP Appendix A** | `mtep_project_events` | Nearby upgrade count and $ investment |
| **GDELT (bounded GKG)** | `news_events` | Rolling `news_count_*`, sentiment |

### Important but sparse / partial

| Source | Silver home | Brings | Caveat |
|--------|-------------|--------|--------|
| **MISO DPP GI Studies** | `miso_dpp_events` / `study_events` | Network upgrade $, delay days, restudy counts | Only dated, high-confidence extracts; Restudy rows allowed for delay chains |
| **EIA-860 plants** | `eia_generator_month` | Operating fleet context | Loaded (~8k) but ~0% exact queue name match |
| **Energy communities** | policy table | IRA siting incentive | ~42% panel coverage by design of the list |

### Registered empty (stubs only — not yet filled)

LMP congestion, federal permits / EPA ECHO, SEC EDGAR, NREL resource, wetlands, BEA GDP, MISO large-load forecasts, BLS construction employment. Schemas exist under `data/silver/enrichment/` so joins can land later without redesign.

---

## Quick start

```bash
source .venv/bin/activate   # or use .venv/bin/python

# 1) Core queue → Silver/Gold
python scripts/run_pipeline.py

# 2) Enrichment framework + sprint (geo, EIA, grid, county, Gold)
python scripts/run_enrichment_sprint.py

# 3) Fill DPP / HIFLD / MTEP / GDELT gaps and rewrite enriched Gold
python scripts/refresh_enrichment_gaps.py
```

Optional: put `EIA_API_KEY=...` in a repo-root `.env` (gitignored). Never commit secrets.

Dependencies: `requirements.txt` / `pyproject.toml`.

Raw GDELT GKG zips are **not** stored in git (~1GB); re-run `refresh_enrichment_gaps.py` (or `ingest_gdelt`) to regenerate Bronze. Silver `news_events.parquet` **is** committed.

---

## Pipeline stages

1. **Ingest** — hash + copy to Bronze; source registry  
2. **Profile** — DQ reports; do not join until gates pass  
3. **Standardize** — canonical schema  
4. **Crosswalk** — Berkeley ↔ MISO; project → county / developer  
5. **Snapshots + outcomes** — mutable fields only on snapshots  
6. **Gold base** — annual classification, survival, current scoring  
7. **Enrichment** — populate Silver enrichment tables; PIT asof / rolling joins into enriched Gold  

Provisional time split (`data/gold/split_manifest.json`): train 2020–2022 · val 2023 · test 2024 · score 2025+ current MISO.

---

## Gold outputs

| Table | Path | Purpose |
|-------|------|---------|
| Annual classification | `data/gold/annual_withdrawal_training/` | `withdraw_next_12m`, `complete_followup`, `next_outcome` |
| Survival | `data/gold/survival_training/` | `(start, stop]` with withdrawal / operation events |
| Current scoring | `data/gold/current_miso_scoring/` | Active MISO, **no** future labels |
| **Enriched training** | `data/gold/withdrawal_panel_enriched.parquet` | Base annual + enrichment features |
| **Enriched scoring** | `data/gold/current_miso_scoring_enriched.parquet` | Same joins for live queue |

Coverage HTML and feature dictionary: `data/quality_reports/enrichment/`.

---

## Design rules (non-negotiable)

- PIT joins only: `available_date ≤ observation_date`  
- Do not invent DPP report dates or broadcast group-total costs to every project  
- Null ≠ zero: unavailable sources stay null until ingested  
- `queue_study_status` = current phase; `miso_dpp_events` = historical study extracts  
- MISO `capacity_mw = max(summer_mw, winter_mw)` (never sum)  
- Hybrids keep component MW; status `Done` → `completed` until MISO docs say otherwise  

---

## Modeling (Phase B — not implemented here)

Do **not** fit preprocessing on validation, test, or current-scoring data. Prefer PR-AUC, Brier/calibration, and top-decile recall over ROC-AUC alone. Ablate feature families (queue / cost / grid / news / macro) and confirm no ID leakage.

Suggested baselines: naive rate → logistic (age, MW, tech) → gradient boosting → discrete-time / competing-risk survival.
