# CatBoost Optuna HPO

- Trials: **50**
- Feature set: **v1**
- Objective: maximize val PR-AUC (test sealed; no calibration)
- Best trial by PR-AUC: **31** (PR-AUC=0.1047)
- Selected finalist trial: **39** (PR/LogLoss/Brier/ECE compromise)

## Finalist metrics

| metric | value |
|--------|-------|
| `pr_auc` | 0.09570521780005817 |
| `roc_auc` | 0.7464811739402685 |
| `brier` | 0.04304710083161212 |
| `ece` | 0.061729714131593276 |
| `log_loss` | 0.18895454093024042 |
| `precision_at_5pct` | 0.05952380952380952 |
| `precision_at_10pct` | 0.08383233532934131 |
| `recall_at_10pct` | 0.2028985507246377 |
| `lift_at_10pct` | 2.024125661720038 |
| `withdrawn_mw_capture_at_10pct` | 0.18850621561035255 |

Trials: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/hpo/catboost/trials.csv`
