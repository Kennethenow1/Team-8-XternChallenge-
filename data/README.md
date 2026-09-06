# `data/` — project database

One tree for all data. Nothing else is named “Data”.

| Folder | What it is |
|--------|------------|
| [`intake/`](intake/README.md) | Raw queue downloads you drop in |
| [`bronze/`](bronze/README.md) | Immutable hashed source copies |
| [`silver/`](silver/README.md) | Clean tables + PIT enrichment ready to join |
| [`gold/`](gold/README.md) | Modeling panels (labels + features) |
| [`quality_reports/`](quality_reports/README.md) | Coverage / engineering diagnostics |
| [`exports/`](exports/) | Optional CSV mirrors |

```text
data/intake/   →  data/bronze/  →  data/silver/  →  data/gold/
   (downloads)      (copies)         (clean)          (model)
```

## Datasets by prediction role

| Prediction role | Examples | Why it matters |
|-----------------|----------|----------------|
| **Queue friction** | age, study phase, capacity, service dates | Stuck projects withdraw more often |
| **Study / cost shock** | DPP upgrade $, delay, restudy | Bad study economics → exit |
| **Grid congestion** | same-POI crowding, distance to line, MTEP | Harder interconnection |
| **Developer track record** | prior withdrawal / completion rates | Sponsor quality |
| **Local market / risk** | population, FEMA, storms, energy community | Siting & incentives |
| **Macro / system** | interest rates, MISO demand YoY | Cost of capital & BA stress |
| **News / opposition** | GDELT counts, sentiment | Local opposition |
| **Label** | `withdraw_next_12m` | What we predict (Gold only) |

Full catalog: [`docs/data_catalog.md`](../docs/data_catalog.md).

## What to open for modeling

| Need | Open |
|------|------|
| Full enriched training rows | `gold/withdrawal_panel_enriched.parquet` |
| **Model-ready / logistic / tree matrices** | `gold/modeling/model_ready_*.parquet`, `logistic_ready_*`, `tree_ready_*` |
| Live queue to score | `gold/current_miso_scoring_enriched.parquet` |
