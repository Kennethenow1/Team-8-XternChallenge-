# Model-ready matrices

`model_ready_{train,val,test,score}.parquet` — numeric feature matrices after
approved collapse / derive transforms (not statistical regularization).
One-hot / drop schema is **frozen from train**.

## Preprocessing outputs

Via `python scripts/prepare_model_matrices.py` (also run from `analyze_features.py`):

| Pattern | Role |
|---------|------|
| `logistic_ready_*` | Full X; train-median impute + StandardScaler |
| `tree_ready_*` | Full X; NaNs kept |
| **`logistic_v1_*`** | **Default logistic X** (V1 policy subset) |
| **`tree_v1_*`** | **Default tree X** (same columns; NaNs kept) |

V1 policy: [`artifacts/feature_policy_v1.json`](artifacts/feature_policy_v1.json) ·
[`../quality_reports/modeling/feature_policy_v1.md`](../quality_reports/modeling/feature_policy_v1.md)

Exclude `project_key` and `observation_date` from `X`. Label: `withdraw_next_12m`.

Schema: `data/quality_reports/modeling/model_ready_schema.csv`  
Readiness: `data/quality_reports/modeling/model_ready_readiness.md`
