# Pipeline runbook

How to rebuild the point-in-time MISO queue feature store. **This repo does not train models.**

Architecture overview: [architecture.png](architecture.png). Code map: [code_map.md](code_map.md). Paths: [data_layout.md](data_layout.md). Dataset index: [data_catalog.md](data_catalog.md). Folder explainers: [`data/`](../data/README.md) · [intake](../data/intake/README.md) · [bronze](../data/bronze/README.md) · [silver](../data/silver/README.md) · [gold](../data/gold/README.md).

## Canonical commands

```bash
source .venv/bin/activate   # or use .venv/bin/python

# 1) Core queue: Bronze → Silver → base Gold
python scripts/run_pipeline.py

# 2) Enrichment (pick the subcommand you need)
python scripts/run_enrichment.py sprint    # usual full refresh
python scripts/run_enrichment.py gaps      # DPP / HIFLD / MTEP / GDELT fill
python scripts/run_enrichment.py panel     # county / FEMA / energy-community only
python scripts/run_enrichment.py skeleton  # light skeletons + populate + Gold
python scripts/run_enrichment.py dpp       # DPP PDF acquire/extract (no Gold merge)

# 3) Train-only modeling prep (no fit on val/test/score)
python scripts/analyze_features.py
python scripts/analyze_features.py --engineer-only
```

Legacy script names (`run_enrichment_sprint.py`, `refresh_enrichment_gaps.py`, …) still work as thin wrappers and print a deprecation note.

Optional CSV mirrors: `python scripts/export_tables_to_csv.py`.

## Which enrichment subcommand?

| Subcommand | Use when |
|------------|----------|
| `sprint` | First enrichment after core pipeline, or refreshing EIA/grid/county + Gold |
| `gaps` | Filling / refreshing DPP extracts, HIFLD distances, MTEP, GDELT news |
| `panel` | Only county population / FEMA / energy-community coverage changed |
| `skeleton` | Need typed empty Silver tables + basic populate without the full sprint extras |
| `dpp` | Downloading / extracting DPP PDFs before they appear in Silver |

Typical order after a clean checkout with intake files present:

`run_pipeline` → `run_enrichment.py sprint` → `run_enrichment.py gaps` → `analyze_features.py`.

## Environment

Put secrets in repo-root `.env` (gitignored). Never commit keys.

| Variable | Used by |
|----------|---------|
| `EIA_API_KEY` | EIA-930 / related market pulls |
| `CENSUS_API_KEY` | Census PEP population (county joins) |

Raw GDELT GKG zips are **not** in git (~1GB). Re-run `run_enrichment.py gaps` (or GDELT ingest) to regenerate Bronze; Silver `news_events.parquet` is committed.

## County / FEMA / energy-community joins

These run via `populate_all(run_deferred_county_joins=True)` inside `sprint` and `skeleton`. Geo FIPS coverage should be healthy before treating county features as reliable (see enrichment quality reports).

Notes:

- Prefer official FEMA NRI ZIP under `data/bronze/fema/` if automated download fails.
- Energy-community lists are versioned by effective date range; joins use `available_date`.
- Do not back-apply a single late population estimate to earlier observation years.

## Design rules (non-negotiable)

- PIT joins only: `available_date ≤ observation_date`
- Do not invent DPP report dates or broadcast group-total costs to every project
- Null ≠ zero: unavailable sources stay null
- `queue_study_status` = current phase; `miso_dpp_events` = historical study extracts
- Deprecated: `data/silver/external/` stubs (still seeded by core pipeline for compatibility; live features live in `data/silver/enrichment/`)

## Outputs to trust

| Artifact | Path |
|----------|------|
| Enriched training panel | `data/gold/withdrawal_panel_enriched.parquet` |
| Enriched scoring | `data/gold/current_miso_scoring_enriched.parquet` |
| **Live model-ready train matrix** | `data/gold/modeling/model_ready_train.parquet` |
| Enrichment coverage | `data/quality_reports/enrichment/` |
| Feature analysis / engineering reports | `data/quality_reports/modeling/` |

Provisional time split (`data/gold/split_manifest.json`): train 2020–2022 · val 2023 · test 2024 · score 2025+ current MISO.
