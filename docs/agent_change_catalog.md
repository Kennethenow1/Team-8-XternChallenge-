# Agent change catalog (two-agent audit trail)

Living log of what you asked Cursor agents to do, **why**, and **what landed**. Use this when switching agents so neither re-does finished work or contradicts the other.

**Current handoff:** Phase 1 core leaves are partly live: trees + **calibration** (`scripts/run_calibration.py`), **Cox-TV / survival tournament**, **TimesFM-3** system forecast. Eval = calibrated \(P(W_{12m})\) + Precision/Recall/MW Capture@10%. Phase 2 simulator still goal-only.

| Agent | Thread focus | Transcript |
|-------|--------------|------------|
| **A** | Pipeline, enrichment, DPP/gaps, feature prep, repo organize, pushes | [PIT pipeline & enrichment](6a3bf4c3-449e-41ad-8cdc-cfca3b587e06) |
| **B** | EIA/Census APIs, CSV export, project-goal reframing, this catalog | [EIA / Census / goal](ae1ec79d-26b4-420f-aa52-ae2563d72fab) |

---

## 1. Foundation — point-in-time B–S–G database

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-04 | A | Build a **point-in-time project database**, not one giant merged table | Avoid leakage; keep observation-date honesty | Bronze–Silver–Gold pipeline: ingest, standardize, crosswalks, snapshots, outcomes, gold labels | Done |
| 2026-09-04 | A | Implement PIT Queue Database plan | Execute the architecture | `scripts/run_pipeline.py`, `src/` layers, `data/bronze|silver|gold`, registries | Done |
| 2026-09-05 | A | Run the pipeline | Materialize tables | Core queue tables populated from Berkeley + MISO sources | Done |
| 2026-09-05 | A | Simple current state of the dataset | Know what exists | Status summary (Q&A) | Q&A only |

---

## 2. Enrichment — feature store, sprint, DPP, gap fills

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-05 | A | Required enrichment datasets (grid, weather, policy, …) | Withdrawal risk needs external PIT context | Plan for enrichment feature store | Done (plan) |
| 2026-09-05 | A | Implement enrichment feature store | Typed silver tables + gold joins | `configs/enrichment_registry.yaml`, `src/enrichment/*`, skeletons, `run_enrichment_pipeline.py` | Done |
| 2026-09-05 | A | Enrichment content only partial — next bottleneck | Structure done, data thin | Enrichment data sprint plan (geo → EIA → grid) | Done (plan) |
| 2026-09-05 | A | Implement enrichment sprint | Fill geo gate, EIA-860, FRED/grid stubs, county joins | `scripts/run_enrichment_sprint.py`, geo crosswalk, partial fills | Done |
| 2026-09-05 | A | Current state + what to do to complete | Prioritize remaining gaps | Status / backlog (Q&A) | Q&A only |
| 2026-09-05 | A | **Historical MISO DPP only** — no models, no other populate | Highest-value study features are missing | DPP harvest/ingest path (`run_miso_dpp_ingest.py`, study/DPP silver tables) | Done (partial harvest) |
| 2026-09-05 | A | Run scripts to populate everything / “nice complete dataset” | Want usable enriched gold | Sprint/populate runs; many enrichment tables still thin | Done (partial) |
| 2026-09-05 | A | What can I do to make solid data (not empty)? | Prioritize high-ROI fills | Guidance: population years, DPP gold, FEMA/EC | Q&A → led to next plan |
| 2026-09-05 | A | Fix population ~48%, DPP noise, FEMA/EC | Coverage and honesty gaps | Popest multi-year, DPP gold filters, FEMA ArcGIS / EC downloads | Done (improved; EC still incomplete vs versioned Treasury design) |
| 2026-09-05 | A | Push with “overall state of data” message | Share progress | Remote push (Agent A) | Done |
| 2026-09-05 | A | Fill DPP, GDELT, HIFLD, MTEP gaps | Remaining empty registered sources | Gap refresh scripts / partial harvests; many still stubs | Done (partial) |
| 2026-09-05 | A | Complete status of datasets and what each brings | Document predictive role of each source | README / data catalog updates | Done |
| 2026-09-05 | A | Push with current database state in message | Checkpoint | Remote push (Agent A) | Done |

---

## 3. API / contextual features (Agent B focus)

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-05 | B | Where to create `.env` for API key | Unlock EIA-930 | Guidance: repo-root `.env`; note process did not yet load dotenv | Q&A → led to implement |
| 2026-09-05 | B | EIA now; FEMA / Census / EC after FIPS | Repair contextual features in priority order | Plan: EIA hourly + dotenv; defer county joins | Done (plan) |
| 2026-09-05 | B | Implement EIA plan | Live MISO demand/generation context | `python-dotenv`, `.gitignore` `.env`, hourly `region-data` D/NG/TI, `miso_*` gold features, `RUN_DEFERRED_COUNTY_JOINS`, `DEFERRED_COUNTY_JOINS.md`, key scrubbing in bronze | Done |
| 2026-09-05 | B | What data do I have? Can it all be CSV? | Inventory + Excel/share access | Inventory Q&A; CSV possible for tables, not all bronze | Q&A only |
| 2026-09-05 | B | Yes (export CSVs) / run it | Materialize shareable tables | `scripts/export_tables_to_csv.py` → `data/exports/csv/` (gitignored) | Done |
| 2026-09-05 | B | Any sentiment analysis in the dataset? | Check if news NLP exists | Schema stubs only; `news_events` empty; features `unavailable` | Q&A only |
| 2026-09-05 | B | What hasn’t been integrated yet? | Gap list for dual-agent planning | DPP / news / HIFLD / MTEP / deferred FEMA·Census·EC / registered_empty sources | Q&A only |
| 2026-09-05 | B | How do I wire Census PEP 2020–2023? | Official multi-year vintage API | How-to (CSV already had years; API path missing) | Q&A → led to implement |
| 2026-09-05 | B | Census key is now in `.env` | Enable API path | `pep/charv` for 2020–2023, `pep_vintage`, YoY / change-since-2020, gold attach | Done |

---

## 4. Modeling prep (Agent A focus)

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-06 | A | What happened to data before gold? | Understand transforms | Pipeline explanation (Q&A) | Q&A only |
| 2026-09-06 | A | Expert: loop / analyze features before modeling | Avoid blind training | Feature analysis plan | Done (plan) |
| 2026-09-06 | A | Plan and run feature analysis | Numeric readiness + collapse screen | `scripts/analyze_features.py`, reports under `data/quality_reports/modeling/` | Done |
| 2026-09-06 | A | Apply expert cluster collapse recommendations | Reduce redundant features | Collapse transforms + macro grain audit (`engineer_features.py`, collapse reports) | Done |
| 2026-09-06 | A | Analyze again / live state vs old collapse docs | Stale reports confusion | Re-ran analysis; clarified live vs cached reports | Done |
| 2026-09-06 | A | Push current modeling state | Checkpoint | Remote push (Agent A) | Done |
| 2026-09-06 | A | Model-ready train: dtypes, roles, scaling, encoding | Know what goes into \(X\) | `model_ready_*`, `model_ready_readiness.md`, `model_ready_schema.csv` | Done |
| 2026-09-06 | A | Train-only preprocessing notes (impute/scale trees vs logistic) | Correct leakage-safe prep | `prepare_model_matrices.py`, logistic/tree ready notes, sparse flags | Done |
| 2026-09-06 | A | Explain / run prep commands; link files | Usability | Commands run; paths linked | Done |
| 2026-09-06 | A | V1 logistic feature policy + ablation packs | Capacity log1p, drop constant missings, ablation sets | `data/gold/modeling/artifacts/feature_policy_v1.json`, `feature_columns_v1.json` | Done |
| 2026-09-06 | A | Rerun command + link / push | Refresh artifacts + share | Artifacts refreshed; push (Agent A) | Done |
| 2026-09-06 | B | Dtypes / making numbers for modeling | Same theme from other agent | Discussed readiness; Agent A owned matrices | Coordinated (no duplicate rewrite) |

---

## 5. Docs / repo hygiene

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-06 | A | Organize codebase + document clearly | Repo felt scattered | `docs/` layout (`data_layout`, `pipeline`, `code_map`, `data_catalog`, …), clearer `data/` README structure | Done |
| 2026-09-06 | A | Why two `data` folders? Label by function / prediction role | Confusion between intake vs pipeline | Clarified `Data/` vs `data/`; catalogs by predictive role; naming improvements | Done |
| 2026-09-06 | A | Show DB state after reorganization | Confirm usability | Status summary | Q&A only |
| 2026-09-06 | B | Reframe Phase 1 as input to **policy-response simulator** | Larger research goal than “why risky” | [`docs/project_goal.md`](project_goal.md); README intro rewritten | Done |
| 2026-09-06 | B | Add **Precision/Recall/MW Capture@10%** as operational eval | Usefulness beyond calibrated \(P(W)\) for Phase 2 stress | Eval section in `project_goal.md`; README note; `operational_metrics` docstring (metrics already in `eval_protocol.py`) | Done |
| 2026-09-06 | B | Install **TimesFM-3**; fix **calibration** + **Cox-TV / full survival** as Phase 1 core | Architecture honesty — leaves were scaffolded | `timesfm[torch]` dep; real TimesFM-3 wrapper; `scripts/run_calibration.py`; `fit_cox_tv` + tournament ops metrics; sksurv for RSF | Done |

---

## 6. This catalog

| Date | Agent | You asked | Why | What changed | Status |
|------|-------|-----------|-----|--------------|--------|
| 2026-09-06 | B | Catalog all changes across both agents: ask → why → what | Dual-agent audit trail | This file; README link | Done |
| 2026-09-06 | B | (extend) Document ops @10% metrics in catalog handoff | Keep dual-agent eval framing aligned | Handoff + docs/hygiene row above | Done |

---

## Explicitly deferred / not done

| Item | Reason | Owner hint |
|------|--------|------------|
| Versioned Energy Communities (Treasury effective windows) | Waited on FIPS / tract; old list partial | Future enrichment |
| FEMA NRI v1.20 full score suite + PIT backcast doc | Deferred with county joins; ArcGIS partial risk only | Future enrichment |
| Full DPP PDF extraction (upgrade cost / restudy dense) | Harvest partial; still highest overall priority | Agent A path |
| News / GDELT sentiment populated | Schema only; 0% on panel | Future enrichment |
| HIFLD distance / MTEP events | Probes/stubs | Future enrichment |
| Phase 2 episode table + rules/policy table + \(a^*\) optimizer | Goal documented only | Phase 2 |
| PCA on main withdrawal model | Explicitly **avoid** unless validated | Modeling |

---

## Key artifacts (quick map)

| Artifact | Path |
|----------|------|
| Project goal | `docs/project_goal.md` |
| Enriched training panel | `data/gold/withdrawal_panel_enriched.parquet` |
| Model-ready splits | `data/gold/modeling/model_ready_{train,val,test,score}.*` |
| Feature policy v1 | `data/gold/modeling/artifacts/feature_policy_v1.json` |
| CSV exports | `data/exports/csv/` (via `scripts/export_tables_to_csv.py`) |
| Calibration summary | `data/gold/modeling/artifacts/metrics/calibration_summary.md` |
| Survival tournament | `data/gold/modeling/artifacts/metrics/survival_tournament.md` |
| TimesFM system forecast | `data/gold/modeling/artifacts/metrics/timesfm_system_forecast.md` |
| Deferred county joins note | `data/quality_reports/enrichment/DEFERRED_COUNTY_JOINS.md` |
| Enrichment sprint | `scripts/run_enrichment_sprint.py` |
| Core pipeline | `scripts/run_pipeline.py` |

---

## How to extend this log

When either agent finishes a non-trivial request, append one row:

`Date | Agent | You asked | Why | What changed | Status`

Keep **Why** to one sentence (intent), **What changed** to paths or “Q&A only.”
