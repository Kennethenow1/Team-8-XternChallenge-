# Data layout

Everything lives under **`data/`**:

| Folder | Role | README |
|--------|------|--------|
| `data/intake/` | Raw queue downloads you drop in | [intake/README.md](../data/intake/README.md) |
| `data/bronze/` | Immutable hashed source copies | [bronze/README.md](../data/bronze/README.md) |
| `data/silver/` | Clean + PIT enrichment tables | [silver/README.md](../data/silver/README.md) |
| `data/gold/` | Labeled / scoring modeling panels | [gold/README.md](../data/gold/README.md) |
| `data/quality_reports/` | Coverage / engineering diagnostics | [quality_reports/README.md](../data/quality_reports/README.md) |

Full source → prediction-role index: [data_catalog.md](data_catalog.md). Overview: [data/README.md](../data/README.md).

```
data/
  intake/                     # drop Berkeley / MISO downloads here
  bronze/                     # immutable source copies
    berkeley/ miso/
    enrichment/               # DPP, HIFLD, MTEP, GDELT, Census, …
  silver/
    projects/ snapshots/ outcomes/
    crosswalks/
    enrichment/               # typed PIT feature tables
    external/                 # deprecated stubs
  gold/
    annual_withdrawal_training/
    survival_training/
    current_miso_scoring/
    withdrawal_panel_enriched.*
    current_miso_scoring_enriched.*
    modeling/model_ready_train.*
    split_manifest.json
  quality_reports/
    enrichment/ modeling/
  exports/csv/
```

## Bronze / Silver / Gold (short)

| Layer | Meaning |
|-------|---------|
| **Bronze** | Immutable hashed copies of sources |
| **Silver** | Clean tables; enrichment has `available_date` for PIT joins |
| **Gold** | Modeling panels (labels + covariates) |

## Gold layout note

- **Base** Gold tables live in **subdirectories**.
- **Enriched** panels are **flat files** at `data/gold/*.parquet`.
- **Modeling matrix** lives under `data/gold/modeling/`.

## Modeling vs quality reports

| Artifact | Meaning |
|----------|---------|
| `data/gold/modeling/model_ready_train.parquet` | **Live** model-ready train matrix |
| `data/quality_reports/modeling/train_numeric_preview.parquet` | Pre-collapse preview |
| `data/quality_reports/modeling/collapse_recommendations.md` | Pre-engineering suggestions only |
| `data/quality_reports/modeling/feature_engineering_notes.md` | What was actually applied |

## Config registries

- `configs/source_registry.yaml` — core queue intake (`data/intake/…`)
- `configs/enrichment_registry.yaml` — external sources + status
