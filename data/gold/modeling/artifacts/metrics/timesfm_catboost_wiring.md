# TimesFM → CatBoost covariate wiring (VAL only)

PIT-safe year-grain system forecasts joined onto `catboost_native_v1` (history year < observation year). Matched **CPU** CatBoost defaults (seed 42, early stop on LogLoss). TEST sealed.

Forecast table: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/features/system_forecast_covariates.parquet`

Note: panel grain is annual (~7 snapshots). TimesFM needs ≥3 history points, so train years 2020–2022 often lack TimesFM values; VAL year forecasts are constant within-year (system-level signal). TimesFM backend: **timesfm-3.0** for observation years ≥2023.

## VAL metrics

| Arm | PR-AUC | ROC | LogLoss | MW@10% | n_feat | status |
|-----|--------|-----|---------|--------|--------|--------|
| catboost_v1 | 0.0806 | 0.6984 | 0.2062 | 0.2237 | 64 | ok |
| catboost_plus_sys_fc_ma3 | 0.0744 | 0.6862 | 0.1951 | 0.2023 | 65 | ok |
| catboost_plus_sys_fc_timesfm | 0.0835 | 0.6950 | 0.2035 | 0.2282 | 65 | ok |
| catboost_plus_sys_fc_all | 0.0787 | 0.6897 | 0.2135 | 0.1911 | 67 | ok |

## Decision

**Rule:** promote interest only if `+sys_fc` beats matched V1 by **≥0.01 PR-AUC** *and* Strong (`pr_auc ≥ 0.10`).

**Best arm:** `catboost_plus_sys_fc_timesfm` (PR-AUC 0.0835, Δ vs V1 = +0.0029)

**Verdict:** catboost_plus_sys_fc_timesfm delta=0.0029 < 0.01 PR-AUC; weak/negative result; leave champion freeze unchanged.

Promote interest: **False**. Champion freeze / TEST seal unchanged unless promote.
