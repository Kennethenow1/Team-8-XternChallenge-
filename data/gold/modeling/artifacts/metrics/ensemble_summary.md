# Ensemble summary (validation only)

Models: `['catboost_tuned', 'lightgbm_tuned', 'xgboost_tuned']`

## Equal weight

- PR-AUC=0.12593668958404583 ROC=0.8010445309593167 Brier=0.04172198019689737 LogLoss=0.18732802695247305 MW@10%=0.28632565722437336

## Optimized (pr_auc)
- Weights: `{'catboost_tuned': 0.3333333333333333, 'lightgbm_tuned': 0.3333333333333333, 'xgboost_tuned': 0.3333333333333333}`
- PR-AUC=0.12593668958404583 Brier=0.04172198019689737 LogLoss=0.18732802695247305

## Optimized (log_loss)
- Weights: `{'catboost_tuned': 0.9995081799316158, 'lightgbm_tuned': 0.00017184479750993525, 'xgboost_tuned': 0.00031997527087422616}`
- PR-AUC=0.12134404448088158 Brier=0.04069961302094164 LogLoss=0.15637815327067656
