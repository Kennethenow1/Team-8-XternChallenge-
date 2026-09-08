# Preprocessing notes (train-only)

## Five model-specific paths

| Path | Role |
|------|------|
| `logistic_v1_*` | Median impute + StandardScaler + one-hot |
| `tree_v1_*` | NaNs + one-hot (XGBoost) |
| `catboost_native_v1_*` | Native cats; numeric NaNs; no scale |
| `foundation_v1_*` | Native cats for TabICL / TabPFN; no external scale |
| `tabm_v1_*` | Int cats + median impute + scale numerics |

## A. Scaling
Logistic: `StandardScaler` on continuous columns, train-fit.
XGBoost / CatBoost / foundation TFMs: no external scaling.
TabM: train StandardScaler on numerics only.

## B. Imputation
Logistic / TabM numerics: train-median. Trees / CatBoost / foundation: leave NaNs.

## C. Sparse ablation
See `sparse_feature_flags.md` — especially `years_since_last_change`.

## D. Macros
Low nunique on annual panel; do not collapse. See `macro_grain_audit.json`.

## V1 / foundation counts
- logistic/tree V1: **85** cols
- foundation / catboost-native: **64** cols
- tabm_v1: **64** cols

Architecture: `docs/model_architecture.md`. Eval: `eval_protocol.md`.
Artifacts: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts`
