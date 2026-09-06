# Preprocessing notes (train-only)

## A. Scaling
Logistic / SVM / NN: `StandardScaler` on continuous `Yes*` columns, fitted on train.
Trees: no scaling (`tree_ready_*`).

## B. Imputation
Logistic: `SimpleImputer(strategy=median)` on all X columns, train-fit.
Keep `*_missing` / `*_available` indicators. Trees leave NaNs.

## C. Sparse ablation
See `sparse_feature_flags.md` — especially `years_since_last_change`.

## D. Macros
Low nunique on annual panel; do not collapse. See `macro_grain_audit.json`.

## V1 feature policy
Default modeling `X`: **85** columns → `logistic_v1_*` / `tree_v1_*`.
See `feature_policy_v1.md` for drops, reference dummies, and ablation packs.

Artifacts: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts`
