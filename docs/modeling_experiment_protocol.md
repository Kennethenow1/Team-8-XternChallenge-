# Modeling experiment protocol

Locked rules for Phase 1 withdrawal models. Architecture: [`model_architecture.md`](model_architecture.md).

## Sealed test

| Split | Use |
|-------|-----|
| **train** | Fit / ICL context only |
| **val** | Metrics, early stopping, HPO, model selection, calibration / ensemble weights |
| **test** | **Sealed** until architecture is frozen (`final_evaluate.py`) |
| **score** | Scoring only; incomplete follow-up — not supervised selection |

Every HPO trial: `fit(train) → predict(val) → metrics`. Never touch test during tuning.

## Sanity baselines (do not mix train and val)

| Reference | Approx value |
|-----------|----------------|
| **Val** prevalence / no-skill PR-AUC | ≈ **0.041** (~4.14%) |
| Val constant-\(p_{\mathrm{val}}\) Brier | ≈ \(p(1-p)\) ≈ **0.040** |
| Constant ROC-AUC | **0.500** |
| Train prevalence (descriptive only) | ≈ **0.124** |

Anything serious must beat the **val** no-skill PR-AUC on validation — not the train prevalence.

## Five matrix paths

| Model | Matrix |
|-------|--------|
| L2 / Elastic-Net logistic | `logistic_v1_*` |
| XGBoost | `tree_v1_*` |
| CatBoost | `catboost_native_v1_*` |
| TabICLv2 / TabPFN-3 | `foundation_v1_*` |
| TabM | `tabm_v1_*` |

No SMOTE / undersampling by default. Imbalance ablations (`class_weight`, `scale_pos_weight≈7`) are later experiments.

## Phase A (done)

Default baselines → [`data/gold/modeling/artifacts/metrics/val_baseline_leaderboard.md`](../data/gold/modeling/artifacts/metrics/val_baseline_leaderboard.md)

```bash
python scripts/prepare_model_matrices.py
python scripts/run_baseline_leaderboard.py
```

## This pass (val baselines → drift → CatBoost)

```bash
python scripts/run_drift_audit.py
python scripts/run_catboost_macro_ablation.py   # picks HPO feature set
python scripts/run_catboost_hpo.py --n-trials 50
```

- Label/followup + train→val drift under `artifacts/metrics/`.
- Ops metrics on CatBoost / HPO: Precision@5/10%, Recall@10%, Lift@10%, Withdrawn-MW-Capture@10%.
- **No calibration** in this pass.

## Phase B — revised order after CatBoost tuned

1. **CatBoost Optuna** (~50) — primary path (`src/modeling/tune.py` / `scripts/run_catboost_hpo.py`).
2. **TabM Optuna** (~30–50; official package if usable).
3. **XGBoost Optuna** (~40–50, shallow/regularized).
4. **TabPFN/TabICL** implementation sanity only (class-1 proba, foundation matrix, checkpoint) — **no large HPO** if still ≈ random.
5. **Ablations** (DPP / years / capacity) on top 2–3 only.
6. **Calibration** then **ensemble** (still test-sealed).
7. Survival / TimesFM / AutoGluon as later ceiling work.
8. **Unlock test** once via `final_evaluate.py`.

HPO objective: **PR-AUC**; prefer high PR-AUC + intact LogLoss/Brier/ECE among top trials. Tree early stop on **LogLoss**.

## Artifact layout

```text
data/gold/modeling/artifacts/
  preprocessing/
  models/{logistic_l2,logistic_elasticnet,catboost,xgboost,tabicl,tabpfn,tabm,catboost_tuned}/
  predictions/
  metrics/
  hpo/catboost/
  calibration/
```

Each successful model saves: model blob, `hyperparameters.json`, `feature_list.json`, `train_metadata.json`, `val_predictions.parquet`, `metrics.json`.
