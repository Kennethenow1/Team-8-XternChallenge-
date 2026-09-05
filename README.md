# Team 8 — Point-in-Time MISO Queue Database

Bronze–Silver–Gold pipeline that builds **point-in-time** project observations for MISO interconnection queue withdrawal modeling.

Each training row means:

> Everything legitimately known about project \(i\) on observation date \(t\). Did it withdraw during the following 12 months?

## Layer rules

| Layer | Path | Rule |
|-------|------|------|
| Intake | `Data/` | Original downloads (staging) |
| **Bronze** | `data/bronze/` | **Immutable copies.** Never edit. Re-ingest only via hash-checked copy. |
| Silver | `data/silver/` | Standardized projects, snapshots, outcomes, crosswalks |
| Gold | `data/gold/` | Modeling tables (labels only here for supervised sets) |
| DQ | `data/quality_reports/` | Profiles and gate results |

## Quick start

```bash
# From repo root — uses the project venv
source .venv/bin/activate   # or: .venv/bin/python
python scripts/run_pipeline.py
```

Dependencies: see `requirements.txt` / `pyproject.toml`.

## Sources

Registered in [`configs/source_registry.yaml`](configs/source_registry.yaml) and written to `data/source_registry.parquet` on ingest:

- Berkeley / LBNL annual editions (2020–2023) and thru-2024 / thru-2025 workbooks (MISO filter applied in Silver)
- Current MISO queue CSV (`Miso Queue Current 2026.csv`)

`published_at` and `data_as_of_date` control when information was available. The Berkeley 2025 edition describes data through 2025; the MISO file is a later current snapshot.

## Pipeline stages

1. **Ingest** — hash + copy to Bronze; source registry  
2. **Profile** — independent DQ reports; **do not join until gate PASSes**  
3. **Standardize** — canonical schema (`src/common/canonical_schema.py`)  
4. **Crosswalk** — Berkeley ↔ MISO IDs (fuzzy matches → `needs_review` only)  
5. **Master + snapshots + deltas** — mutable fields live only on snapshots  
6. **Outcomes** — separate table (interval-censored uncertain withdrawals)  
7. **Gold** — annual classification, survival, current scoring (no labels)  
8. **External stubs** — grain + `available_at` schemas for future PIT joins  

## Gold tables

| Table | Path | Purpose |
|-------|------|---------|
| Annual classification | `data/gold/annual_withdrawal_training/` | `withdraw_next_12m`, `complete_followup`, `next_outcome` |
| Survival | `data/gold/survival_training/` | `(start, stop]` with withdrawal / operation events |
| Current scoring | `data/gold/current_miso_scoring/` | Active MISO projects, **no** future labels |

Provisional time split (see `data/gold/split_manifest.json`):

- Train: 2020–2022  
- Validation: 2023  
- Test: 2024  
- Score: 2025 Berkeley + current MISO  

## Enrichment feature store

Point-in-time external features live under `data/silver/enrichment/` (do not merge raw enrichment into Gold).

```bash
# Full enrichment (framework + populate)
.venv/bin/python scripts/run_enrichment_pipeline.py

# Data sprint: geo gate → study rename → EIA → grid → county joins → Gold
.venv/bin/python scripts/run_enrichment_sprint.py
```

Put `EIA_API_KEY=...` in a repo-root `.env` (gitignored). Scripts load it via `python-dotenv` and never print the key.

MISO-wide monthly grid features (`miso_mean_demand_mw`, `miso_peak_demand_mw`, `miso_demand_yoy_pct`, `miso_generation_yoy_pct`, `miso_net_interchange_mw`) come from EIA-930 hourly region-data. FEMA NRI / Census PEP / Energy Communities county joins are deferred until FIPS coverage improves — see `data/quality_reports/enrichment/DEFERRED_COUNTY_JOINS.md`.

Does **not** rebuild Berkeley/MISO core tables. Outputs:

- `data/gold/withdrawal_panel_enriched.parquet`
- `data/gold/current_miso_scoring_enriched.parquet`
- `data/quality_reports/enrichment/` (manifest, dictionary, coverage HTML, leakage audit, geo/EIA/developer match review, sprint_summary.json)

`queue_study_status` = current MISO phase snapshot (not historical). `study_events` / `miso_dpp_events` hold dated DPP history when available (empty until PDFs/HTML are parsed).

## Phase B (not implemented yet) — modeling checklist

Do **not** fit preprocessing on validation, test, or current-scoring data.

### Preprocessing (training only)

- Median imputation + missingness indicators  
- `log1p` for skewed capacity/count features  
- Robust scaling for linear models only  
- One-hot for technology/state; rare-category grouping  
- Frequency encoding for high-cardinality POIs  
- Explicit `unknown` category  

Tree models generally do not need standard scaling. Winsorize only in the model pipeline, never in Silver.

### Baselines to compare

1. Naive overall withdrawal rate  
2. Logistic regression (queue age, MW, technology)  
3. Gradient-boosted trees  
4. Discrete-time survival  
5. Competing-risk (withdrawal vs operation)  

### Evaluation (not ROC-AUC alone)

- Precision–recall AUC  
- Brier score + calibration  
- Recall in highest-risk 10% / 20%  
- Performance by year, technology, state  
- Time-dependent survival metrics  

### Leakage and robustness tests (§24)

- Remove IDs and project names from predictors  
- Confirm current MISO values never enter historical Berkeley snapshot rows  
- External features: `available_at <= observation_date`  
- Ablate each feature family  
- Sensitivity to uncertain / `needs_review` matches  
- With vs without partially confirmed outcomes  
- Check whether missingness alone predicts withdrawal  
- Report performance for active, hybrid, storage, and large projects separately  

## Design notes

- MISO `capacity_mw = max(summer_mw, winter_mw)` (never sum)  
- ERIS / NRIS kept separate  
- Status `Done` maps to `completed`, **not** operational, until MISO definition is confirmed  
- Hybrids keep component MW columns; never reduce solar+storage to solar  
- Conflicts retain parallel `berkeley_*` / `miso_*` fields in the crosswalk  
