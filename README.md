# Team 8 — MISO Interconnection Policy-Response Simulator

**Project goal:** use predicted queue withdrawals as inputs to an actionable **policy-response simulator** —

```text
Predicted withdrawals → Expected consequences → MISO response
→ Can MISO modify that response to reduce the consequences?
```

Phase 1 predicts project-level withdrawal risk (\(P(W)\), MW, study/POI context). Phase 2 asks how MISO’s existing response procedures can be modified to minimize downstream cost, delay, restudies, and secondary withdrawals under reliability and regulatory constraints. Full framing: **[docs/project_goal.md](docs/project_goal.md)**.

**This repo’s current deliverable** is the **point-in-time (PIT) feature store** that supports Phase 1 prediction inputs (and future Phase 2 joins). No model training or response optimizer lives here yet.

Each enriched training row means:

> Everything that could legitimately be known about project \(i\) on observation date \(t\) — queue state, study costs, grid context, local risk, news — without using information published after \(t\). Did it withdraw in the following year?

---

## How the database is organized

```
Data/                         # (legacy pointer) → use data/intake/
data/
  intake/                     # Raw queue downloads
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
    modeling/                     # model_ready / logistic_ready / tree_ready
  quality_reports/            # Coverage + modeling readiness
configs/
  source_registry.yaml        # Core queue sources
  enrichment_registry.yaml    # External feature sources + status
scripts/                      # run_pipeline, run_enrichment, analyze_features, …
src/                          # Ingest, standardize, enrich, PIT joins, modeling prep
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

# 1) Core queue → Silver / base Gold
python scripts/run_pipeline.py

# 2) Enrichment
python scripts/run_enrichment.py sprint
python scripts/run_enrichment.py gaps

# 3) Train-only feature engineering + logistic/tree prep matrices
python scripts/analyze_features.py
```

### Windows

PowerShell (CPU, local `.venv`):

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/run_pipeline.py
```

Native Windows TensorFlow / the local `.venv` cannot use CUDA. For GPU (PyTorch + TensorFlow on the NVIDIA card), run through **WSL2 Ubuntu**:

```powershell
.\scripts\wsl-python.cmd scripts\check_cuda.py
.\scripts\wsl-python.cmd scripts\run_pipeline.py
```

Or inside Ubuntu:

```bash
source ~/venvs/team8-miso/bin/activate
cd /mnt/c/Users/<you>/Documents/Team-8-XternChallenge-
python scripts/check_cuda.py
```

In Cursor / Jupyter, pick the **Python 3.12 (WSL CUDA)** kernel for GPU notebooks. The Windows `.venv` kernel stays CPU-only.

See [docs/pipeline.md](docs/pipeline.md), [docs/data_catalog.md](docs/data_catalog.md), [data/README.md](data/README.md).  
Intake downloads live in **`data/intake/`** (not the old capital-`Data/` folder).

Optional: `EIA_API_KEY` / `CENSUS_API_KEY` in repo-root `.env` (gitignored).

---

## Feature analysis (modeling prep)

```bash
python scripts/analyze_features.py              # analysis + engineering + prep
python scripts/analyze_features.py --engineer-only
python scripts/prepare_model_matrices.py        # prep only
```

| Artifact | Role |
|----------|------|
| `data/gold/modeling/model_ready_{train,val,test,score}.parquet` | Frozen-schema engineered matrices |
| `data/gold/modeling/logistic_ready_*.parquet` | Train-median impute + StandardScaler |
| `data/gold/modeling/tree_ready_*.parquet` | Same `X` order; NaNs kept for trees |
| `data/quality_reports/modeling/model_ready_readiness.md` | Dtype/role checklist + A–D prep rules |
| `data/quality_reports/modeling/sparse_feature_flags.md` | Ablation candidates (e.g. `years_since_last_change`) |

Prep fits **only on train**; apply to val/test/score. No model fitting in this step.

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
