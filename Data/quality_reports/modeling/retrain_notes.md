# Retrain rules (locked)

Val-only retrain / amelioration notes. **Do not open** `data/gold/modeling/model_ready_test.parquet` (or any `*_test.parquet` for selection). Selection stays on **val 2023**. Freeze pointer: [`docs/final_model_freeze.md`](../../../docs/final_model_freeze.md).

These rules apply to `scripts/run_retrain_ameliorations.py` and every notebook under [`electrum/`](../../../electrum/).

## Splits stay calendar-based

| Split | Years | Use |
|-------|-------|-----|
| train | 2020–2022 | Fit only |
| val | 2023 | Metrics, early stopping, HPO, promotion |
| test | 2024 | **Sealed** |
| score | 2025–2026 | Scoring only |

**Do not** randomly shuffle rows into train/val/test. **Do not** `train_test_split`. Mixing years leaks the future and makes val look too easy (train dropout ~12% vs val ~4%).

Row **order** inside a split does not matter for PR-AUC / ROC / log-loss. Minibatch shuffle on **train** neural nets is OK. Val loaders stay unshuffled. Platt 5-fold shuffle is OK **inside val** only.

## No PCA on trees

PCA after scaling finds X-cliques (duplicate columns + year-macros with 2–3 unique train values), not columns that predict `withdraw_next_12m`. CatBoost / LightGBM / XGBoost stay **unscaled** and **unrotated**.

If a linear/neural path needs a “flex that implies the label” test, that method is **PLS** on **train numerics only**, never PCA one-hots. PCA-90% variance is a **negative control**, not a ship candidate.

## No 50/50 class resampling

Positive = the project **quits** in 12 months (rare: ~12% train, ~4% val). Do **not** duplicate quitters, drop stayers, or SMOTE. Optional **loss reweight** (`class_weight` / `scale_pos_weight` / CatBoost `auto_class_weights` / focal) is allowed as a val ablation. Dump it if it only flags everyone.

Headline score is **PR-AUC**. Accuracy is logged on NN/boosting curves only; it is a bad headline here (always-stay wins accuracy).

## Strong gates (val)

PR-AUC ≥ 0.10, PR-lift ≥ 2.5, ROC ≥ 0.74, log-loss ≤ 0.195, MW@10% ≥ 0.22.

Promote a change only if it beats unrotated, unweighted **`catboost_tuned`** (trial-149 params, seed 2026) on that set. Test stays sealed until freeze is re-approved.

## Reference hyperparams (trial 149)

Deploy path remains seed **2026** + Platt unless this retrain clearly wins on val. Peak paper number (PR-AUC 0.144) is seed-fragile — see `catboost_champion_seed_stability.md`.

```json
{
  "depth": 5,
  "learning_rate": 0.1324314134827593,
  "l2_leaf_reg": 1.9470294574701563,
  "random_strength": 2.900625533346776,
  "bagging_temperature": 3.703566521912387,
  "border_count": 214,
  "min_data_in_leaf": 32,
  "iterations": 5000,
  "early_stopping_rounds": 100,
  "random_seed": 2026
}
```
