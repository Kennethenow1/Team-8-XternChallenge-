# Retrain val comparison

Selection on **val 2023** only. Test sealed. No PCA on trees. No split shuffle. No 50/50 resampling.

Reference: `catboost_unweighted_seed2026` (trial-149 params, CPU) PR-AUC = **0.074**. Deploy freeze remains **`catboost_tuned` seed 2026 + Platt** until freeze is re-approved.

**Do not promote any new method.** No SHAP trim, MW-weight, sparse drop, news drop, monotone, class-weight, focal, PLS, or PCA variant beat unrotated CatBoost on the Strong gates. Seed 42 of the **same** trial-149 recipe hit PR-AUC **0.144** (the known paper peak). That is seed variance, not a new model. Seed bag (42/123/2026) is more stable (PR-AUC 0.097, best log-loss 0.183) but misses Strong (MW@10% 0.198, PR-lift 2.33).

## Leaderboard

| model | status | pr_auc | pr_lift | roc_auc | log_loss | withdrawn_mw_capture_at_10pct | precision_at_10pct | strong | dump |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| catboost_unweighted_seed2026 | ok | 0.0737 | 1.7787 | 0.6442 | 0.1927 | 0.1630 | 0.0838 | False | False |
| catboost_trial149_seed42 | ok | 0.1444 | 3.4859 | 0.7937 | 0.1873 | 0.3352 | 0.1557 | True | False |
| catboost_trial149_seed123 | ok | 0.0578 | 1.3967 | 0.5683 | 0.1978 | 0.1340 | 0.0599 | False | False |
| catboost_seed_bag_42_123_2026 | ok | 0.0966 | 2.3327 | 0.7246 | 0.1831 | 0.1982 | 0.1018 | False |  |
| catboost_shap_trim | ok | 0.0542 | 1.3079 | 0.5956 | 0.2081 | 0.1381 | 0.0599 | False | False |
| catboost_perm_trim | ok | 0.0405 | 0.9780 | 0.4762 | 0.1888 | 0.0683 | 0.0419 | False | False |
| catboost_mw_sample_weight | ok | 0.0420 | 1.0144 | 0.4801 | 0.2169 | 0.1019 | 0.0419 | False | False |
| catboost_drop_sparse | ok | 0.0689 | 1.6626 | 0.6272 | 0.2096 | 0.1686 | 0.0778 | False | False |
| catboost_drop_news_drift | ok | 0.0554 | 1.3381 | 0.6021 | 0.1894 | 0.1070 | 0.0539 | False | False |
| catboost_monotone | ok | 0.0745 | 1.7989 | 0.6298 | 0.2103 | 0.1978 | 0.0778 | False | False |
| catboost_auto_class_weights | ok | 0.0486 | 1.1725 | 0.5779 | 0.4156 | 0.0820 | 0.0359 | False | True |
| catboost_focal | ok | 0.0608 | 1.4688 | 0.6512 | 0.3279 | 0.0560 | 0.0299 | False | True |
| lightgbm_default | ok | 0.0456 | 1.1007 | 0.5371 | 0.2152 | 0.0611 | 0.0240 | False |  |
| lightgbm_logloss_focus | ok | 0.0377 | 0.9114 | 0.4428 | 0.2137 | 0.0000 | 0.0000 | False |  |
| xgboost_default | ok | 0.0417 | 1.0077 | 0.4577 | 0.2139 | 0.0790 | 0.0479 | False |  |
| xgboost_logloss_focus | ok | 0.0990 | 2.3892 | 0.7667 | 0.2130 | 0.2808 | 0.1257 | False |  |
| logistic_current | ok | 0.0370 | 0.8942 | 0.4684 | 0.2916 | 0.0448 | 0.0240 | False |  |
| logistic_pls | ok | 0.0393 | 0.9490 | 0.4847 | 0.3173 | 0.0958 | 0.0419 | False |  |
| logistic_pca | ok | 0.0406 | 0.9795 | 0.4984 | 0.3591 | 0.0606 | 0.0299 | False |  |

## Strong gates

PR-AUC ≥ 0.10, PR-lift ≥ 2.5, ROC ≥ 0.74, log-loss ≤ 0.195, MW@10% ≥ 0.22.

## What we tried (val only)

| Idea | Outcome |
|------|---------|
| Trial-149 seeds 42 / 123 / 2026 | Fragile: 0.144 / 0.058 / 0.074. Same as freeze seed-stability story. |
| Probability bag of those three | More stable, best log-loss (0.183), **not** Strong. |
| SHAP / permutation drop bottom 20% | Both worse. Do not trim. |
| `sample_weight ∝ capacity_mw` | Worse PR-AUC and MW@10%. Keep unweighted. |
| Drop sparse (≥80% missing numerics) | `years_since_last_change` already V1 HARD_DROP. Remaining sparse drop did not help. |
| Drop news* (high drift); **macros kept** | Worse. Do not auto-drop news or macros. |
| Monotone constraints (cost / queue age / prior quit rate ↑ risk) | ~tied with unconstrained seed 2026, not Strong. |
| `auto_class_weights=Balanced` | **Dump** — mean predicted prob 0.28 vs 4% prevalence; log-loss 0.42. |
| Focal loss | **Dump** — log-loss 0.33, mean prob 0.25; does not rank better. |
| LightGBM log-loss-focused trees | Did not reach Strong; log-loss still ~0.21. |
| XGBoost log-loss-focused (shallower + L2) | Best non-CatBoost rank (PR-AUC 0.099, ROC 0.767, MW@10% 0.281) but log-loss 0.213 misses Strong. |
| Logistic current vs PLS vs PCA-90% | All ~chance. PCA negative control is not better in a useful way. PLS does not beat trees. |

## Cold-start slices (seed-2026 CatBoost)

| slice | status | n | pr_auc | log_loss | withdrawn_mw_capture_at_10pct | reason |
| --- | --- | --- | --- | --- | --- | --- |
| never_in_training | ok | 121 | 0.1252 | 0.3334 | 0.0373 |  |
| seen_in_training | ok | 1545 | 0.0738 | 0.1817 | 0.1914 |  |
| new_developer | skipped | 7 |  |  |  | too few positives |
| seen_developer | ok | 1659 | 0.0740 | 0.1932 | 0.1630 |  |

Never-seen projects (n=121) rank a bit better on PR-AUC but MW capture is worse and log-loss is poor. Do **not** train a separate cold-start model at this n. New-developer n=7 is too small.

## Locked rules

See [`retrain_notes.md`](retrain_notes.md). Machine-readable: `data/gold/modeling/artifacts/metrics/retrain_ameliorations.json`.

Runnable family notebooks (you run 01→11): [`electrum/`](../../../electrum/).
