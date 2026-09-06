# Sparse feature flags (ablation candidates)

Numeric features with missing ≥ **80%** on train `model_ready`.
Do **not** auto-drop. Protocol: **Model A** with feature, **Model B** without — compare **validation** metrics.

## Callout: `years_since_last_change`

- missing %: **97.681**
- non-null train rows: **76**
- Extremely sparse — test with vs without on validation before keeping.

## All sparse numerics

| feature | missing % | n_non_null |
|---------|-----------|------------|
| `years_since_last_change` | 97.681 | 76 |
| `capacity_reduction_pct` | 93.226 | 222 |
| `cost_change_since_previous_study` | 92.402 | 249 |
| `upgrade_cost_per_mw` | 89.442 | 346 |
| `study_delay_days` | 89.319 | 350 |
| `network_upgrade_cost` | 84.803 | 498 |
