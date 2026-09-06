# `data/intake/` — raw queue downloads

Drop original Berkeley / MISO queue files here. The pipeline **copies** them into `data/bronze/` with hashes; it does not rewrite these files.

This replaced the old confusing capital-`Data/` folder. Everything under **`data/`** is now one tree:

`intake/` → `bronze/` → `silver/` → `gold/`

## Files typically here

| File | Source | Used for |
|------|--------|----------|
| `lbnl_ix_queue_data_file_thru2024_v2.xlsx` / `…thru2025.xlsx` | LBNL / Berkeley Lab IX queue | Historical projects → `bronze/berkeley` |
| `queues_2020_clean_data.xlsx` … `queues_2023_…` | Annual clean queue extracts | Vintage Berkeley intakes |
| `Miso Queue Current 2026.csv` | MISO public queue | Current MISO → `bronze/miso` |

After adding files, ensure `configs/source_registry.yaml` lists them, then:

```bash
python scripts/run_pipeline.py
```

External enrichment (DPP, HIFLD, GDELT, …) is stored under `data/bronze/enrichment/`, not here.

See also: [`../README.md`](../README.md) · [`../bronze/README.md`](../bronze/README.md)
