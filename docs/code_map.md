# Code map

Where logic lives. Prefer the scripts in [pipeline.md](pipeline.md); this page is for navigating `src/`.

Enrichment modules are **flat** under `src/enrichment/` (no ingest/populate/join subpackages yet).

## Packages

| Package | Role |
|---------|------|
| [`src/common/`](../src/common/) | Paths, canonical schema, status/tech maps, normalization |
| [`src/bronze/`](../src/bronze/) | Hash-checked ingest + source profiling |
| [`src/silver/`](../src/silver/) | Standardize queues, snapshots, outcomes, Berkeley↔MISO crosswalk |
| [`src/gold/`](../src/gold/) | Base training / survival / scoring tables (no external enrichment) |
| [`src/enrichment/`](../src/enrichment/) | External ingest, Silver populate, PIT joins into enriched Gold |
| [`src/modeling/`](../src/modeling/) | Train-only feature analysis + engineering (no model fit yet) |

Registries: YAML under [`configs/`](../configs/) plus [`src/enrichment/registry.py`](../src/enrichment/registry.py). There is no separate `src/registry` package.

## `src/common`

| Module | Role |
|--------|------|
| `paths.py` | Repo roots under `data/` (`intake`, bronze, silver, gold) |
| `canonical_schema.py` | Shared column contracts |
| `normalize.py` | String / ID cleaning helpers |
| `status_map.yaml` / `technology_map.yaml` | Ontology maps (see also [mappings.md](mappings.md)) |

## `src/bronze`

| Module | Role |
|--------|------|
| `ingest.py` | Copy intake → bronze with hashes; update source registry |
| `profile_source.py` | DQ profiles before joining |

## `src/silver`

| Module | Role |
|--------|------|
| `standardize_berkeley.py` / `standardize_miso.py` | Canonical project tables |
| `crosswalk.py` | Berkeley ↔ MISO project keys |
| `build_master_snapshots.py` | Point-in-time queue snapshots |
| `build_outcomes.py` | Withdrawal / completion outcomes |
| `external_stubs.py` | **Deprecated** empty stubs under `data/silver/external/` (still called from core pipeline) |

## `src/gold`

| Module | Role |
|--------|------|
| `build_training.py` | Annual classification, survival, current scoring Gold |

## `src/enrichment`

| Module | Role |
|--------|------|
| `env.py` | Load `.env` for API keys |
| `registry.py` | Paths + ensure enrichment dirs |
| `skeletons.py` | Typed empty Silver enrichment tables |
| `build_crosswalks.py` | Geo / developer / EIA plant crosswalks |
| `populate.py` | Open sources + county/FEMA/EC (`run_deferred_county_joins`) |
| `study_tables.py` | Queue study status + DPP index harvest |
| `ingest_miso_dpp.py` | DPP PDF acquire / extract / re-extract |
| `ingest_eia860.py` | EIA-860 plant inventory |
| `ingest_mtep.py` | MTEP Appendix A harvest |
| `ingest_gdelt.py` | Bounded GDELT GKG news |
| `grid_pressure.py` | HIFLD lines, POI distance, related grid context |
| `pit_join.py` | Point-in-time asof / rolling join helpers |
| `build_enriched_gold.py` | Join enrichment onto annual + scoring panels |
| `reports.py` | Coverage / dictionary / HTML reports |

## `src/modeling`

| Module | Role |
|--------|------|
| `feature_analysis.py` | Train inventory, numeric preview, high-corr screen → quality_reports |
| `feature_engineering.py` | Approved collapses → `model_ready_{train,val,test,score}` |
| `preprocessing.py` | Train-only median impute + StandardScaler → `logistic_ready_*`; `tree_ready_*` keeps NaNs; emits `*_v1_*` |
| `feature_policy.py` | V1 default drops / reference dummies / ablation packs |

## Scripts (entrypoints)

| Script | Role |
|--------|------|
| `scripts/run_pipeline.py` | Core Bronze→Silver→Gold |
| `scripts/run_enrichment.py` | Canonical enrichment CLI (`sprint` \| `gaps` \| `panel` \| `skeleton` \| `dpp`) |
| `scripts/analyze_features.py` | Analysis + engineering (`--engineer-only` supported) |
| `scripts/export_tables_to_csv.py` | Parquet → `data/exports/csv/` |

Other `scripts/*enrichment*` / `engineer_features.py` names are **wrappers** only.
