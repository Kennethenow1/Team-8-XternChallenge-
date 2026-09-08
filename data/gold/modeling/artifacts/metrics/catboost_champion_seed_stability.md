# CatBoost champion seed stability (trial 149)

Bounded re-fit of champion hyperparameters on seeds **42 / 123 / 2026** (VAL only; TEST sealed).

- PR-AUC mean±std: **0.0801 ± 0.0274** (min 0.0569, max 0.1186)
- MW@10% mean±std: **0.1631 ± 0.0451**
- HPO peak (trial 149 @ seed 42 during search): **0.1444**

| seed | pr_auc | roc_auc | log_loss | mw@10% | goal | meets_strong |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | 0.0569 | 0.6378 | 0.2039 | 0.1350 | below_strong | False |
| 123 | 0.0647 | 0.6792 | 0.1939 | 0.1275 | below_strong | False |
| 2026 | 0.1186 | 0.7847 | 0.1598 | 0.2267 | strong | True |

## Decision

- **Keep champion:** `catboost_hpo_trial_149`
- **Promote seed-mean model:** **False**
- Seed-mean PR-AUC does not clearly beat the HPO peak while remaining Strong-stable; keep trial 149 as VAL peak champion. Deployable saved artifact remains catboost_tuned (best multiseed seed from prior promotion) for calibration.

Artifacts: `data/gold/modeling/artifacts/metrics/catboost_champion_seed_stability.csv`, `data/gold/modeling/artifacts/metrics/catboost_champion_seed_stability.json`, models under `artifacts/models/catboost_champion_seed_*`.
