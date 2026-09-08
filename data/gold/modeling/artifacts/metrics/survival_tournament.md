# Survival tournament (validation only)

**Test / score sealed.** 12m risk aligned to modeling val where possible.

| model | status | pr_auc | roc_auc | P@10% | R@10% | MW@10% | alignment |
|-------|--------|--------|---------|-------|-------|--------|-----------|
| discrete_logistic | ok | 0.03914563404350931 | 0.47066510576896897 | 0.0 | 0.0 | 0.0 | aligned to modeling val: 1666/1666 rows |
| cox_tv | ok | 0.029496198164842256 | 0.3509070449121087 | 0.0 | 0.0 | 0.0 | aligned to modeling val: 1666/1666 rows |
| cox_ph | skipped | None | None | None | None | None | CoxPH fit failed: delta contains nan value(s). Convergence halted. Please see the following tips in the lifelines documentation: https://lifelines.readthedocs.io/en/latest/Examples.html#problems-with-convergence-in-the-cox-proportional-hazard-model |
| boost_lgbm | ok | 0.03794232353332842 | 0.3594148448631039 | 0.0 | 0.0 | 0.0 | aligned to modeling val: 1666/1666 rows |
| xgb_aft | skipped | None | None | None | None | None | XGBoost AFT requires upper_bound kw; not supported in this API version |
| rsf | ok | 0.033181927224253754 | 0.4283212182262031 | 0.0 | 0.0 | 0.0 | aligned to modeling val: 1666/1666 rows |
