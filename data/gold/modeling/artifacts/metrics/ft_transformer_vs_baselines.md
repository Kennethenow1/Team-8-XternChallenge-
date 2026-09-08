# FT-Transformer vs baselines (VAL only)

Protocol: train on TRAIN, evaluate on VAL. TEST/SCORE sealed. Matrix: `ftt_v1` (alias of `tabm_v1` normalize — integer cats + median impute + StandardScaler). FT-Transformer seed 42, early-stopped on VAL PR-AUC (device: cpu; CUDA unavailable in this run).

## VAL metrics

| Model | PR-AUC | ROC | LogLoss | MW@10% | notes |
|-------|--------|-----|---------|--------|-------|
| CatBoost trial 149 | 0.144 | 0.794 | 0.187 | 0.335 | champion (peak) |
| CatBoost tuned | 0.121 | 0.799 | 0.156 | 0.291 | deployable (seed 2026) |
| TabM | 0.056 | 0.615 | 0.195 | 0.114 | prior neural tabular |
| NASNet | 0.056 | 0.508 | 0.566 | 0.068 | closed CNN experiment |
| FT-Transformer | 0.087 | 0.641 | 0.768 | 0.184 | new; seed 42, best epoch 25 |

Sources: `artifacts/champion.json`, `artifacts/models/catboost_tuned/metrics.json`, `artifacts/models/tabm/metrics.json`, `reports/models/nasnet/nasnet_validation_metrics.json`, `artifacts/models/ft_transformer/metrics.json`.

## Decision

**Rule:** promote interest only if FT-T beats TabM materially **and** approaches CatBoost Strong (`pr_auc ≥ 0.10`).

**Verdict:** FT-Transformer is a **weak neural challenger**, not a promotion candidate.

- Beats TabM on PR-AUC (0.087 vs 0.056) and MW@10% (0.184 vs 0.114), but still below CatBoost Strong (0.10) and far from tuned/peak CatBoost.
- Does not approach CatBoost tuned (0.121) or peak champion (0.144).
- Calibration / log-loss remains weak (0.768 vs TabM 0.195 / CatBoost ~0.16–0.19).
- Same qualitative story as TabM/NASNet: neural tabular on this matrix underperforms gradient boosting on native features.

No change to CatBoost champion or deployable package. TEST remains sealed.
