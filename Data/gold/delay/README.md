# Gold delay — COD slip panel

Parallel to withdrawal gold. **Does not replace** `withdraw_next_12m` tables.

## Why 24 months

Berkeley snapshots are year-end (2020-12-31 … 2025-12-31). The 2024 vintage has **zero** `proposed_service_date` / `operational_date` values. A strict 12-month window from 2023-12-31 therefore has no future COD and would leave **val empty**. Labels use the next non-null COD within **24 months** (typically 2023 → 2025). `cod_at_t` is last-known COD with `observation_date ≤ t` (PIT).

MISO `operational_date` is Appl In Service Date, not proven COD. Snapshot revisions of negotiated/appl ISD are the GIQ delay signal. EIA-860M planned COD is an independent check when a fuzzy match exists.

## Artifacts

| Path | Role |
|------|------|
| `cod_delay_panel.parquet` | project × year with `cod_slip_months_next_12m` + companion binary |
| `survival_cod_training.parquet` | intervals, competing operate vs withdraw |
| `split_manifest.json` | calendar splits + `neural_nets_ok` gate |
| `label_audit.json` | labeled counts by year/split / GIA slice |
| `modeling/delay_*_v1_{train,val,test,score}.parquet` | matrix views |
| `modeling/delay_seq_v1_*.npz` | T=12 snapshot sequences for the 1D CNN |

Test 2024 remains **sealed** for selection. Supervised train/val/test rows require a numeric slip label.

Build: `python scripts/run_delay_gold.py`.
