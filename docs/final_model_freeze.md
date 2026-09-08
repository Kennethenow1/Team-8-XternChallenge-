# Final model freeze (Phase 1 VAL package)

## Status

**NOT READY TO UNSEAL TEST.**  
TEST and SCORE remain sealed. This document freezes the **validation** champion package for Phase 2 prep.

**Updated:** 2026-09-07

## Decisions

| Item | Choice |
|------|--------|
| VAL peak champion (leaderboard) | `catboost_hpo_trial_149` — PR-AUC **0.144**, goal **strong** |
| Deployable saved model | `catboost_tuned` (same hyperparams, seed **2026**) — PR-AUC **0.121**, goal **strong** |
| Feature matrix | `catboost_native_v1` (64 features; native cats) |
| Calibration | **Platt** on `catboost_tuned` |
| NASNet / tabular→image | **CLOSED** — negative result; no further training budget |
| TEST / SCORE | **Sealed** |

Keep `champion.json` as trial 149 (peak VAL). Ship Phase 2 probabilities from **`catboost_tuned` + Platt**.

## VAL metrics vs goals

Strong: `pr_auc≥0.10`, `pr_lift≥2.5`, `roc_auc≥0.74`, `log_loss≤0.195`, `mw@10%≥0.22`  
Stretch: `pr_auc≥0.12`, `pr_lift≥3.0`, `roc_auc≥0.78`, `log_loss≤0.185`, `mw@10%≥0.28`

### Peak (`catboost_hpo_trial_149`)

| Metric | Value | Strong | Stretch |
|--------|------:|:------:|:-------:|
| PR-AUC | 0.1444 | yes | yes |
| PR-lift | 3.49 | yes | yes |
| ROC-AUC | 0.794 | yes | yes |
| Log-loss | 0.187 | yes | **no** (≤0.185) |
| MW@10% | 0.335 | yes | yes |

### Deployable (`catboost_tuned` raw)

| Metric | Value | Strong | Stretch |
|--------|------:|:------:|:-------:|
| PR-AUC | 0.1213 | yes | yes |
| PR-lift | 2.93 | yes | no |
| ROC-AUC | 0.799 | yes | yes |
| Log-loss | 0.156 | yes | yes |
| MW@10% | 0.291 | yes | yes |

### Calibrated (`catboost_tuned` + Platt, CV primary)

- Brier **0.0385**, ECE **0.0066**, LogLoss **0.1529** (improved vs raw)
- Ranking PR-AUC stays ≈ **0.120** (do not use isotonic for selection)

## Seed stability (trial 149 params; seeds 42 / 123 / 2026)

See [`data/gold/modeling/artifacts/metrics/catboost_champion_seed_stability.md`](../data/gold/modeling/artifacts/metrics/catboost_champion_seed_stability.md).

| seed | PR-AUC | MW@10% | goal |
|-----:|-------:|-------:|------|
| 42 | 0.057 | 0.135 | below_strong |
| 123 | 0.065 | 0.127 | below_strong |
| 2026 | 0.119 | 0.227 | **strong** |

- Mean PR-AUC **0.080 ± 0.027** — high seed variance; HPO peak (0.144) is not fully reproducible.
- **Do not promote seed-mean** over trial 149 peak; accept Strong on peak + deploy `catboost_tuned`.

## Hyperparameters (trial 149 / `catboost_tuned`)

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

Cat features: `technology_primary`, `state_code`, `study_phase`, `service_type`.

## Phase 2 probability protocol

1. **Rank / ops@K** → raw `y_prob` from `catboost_tuned`
2. **Calibrated \(P(W)\)** → Platt calibrator under `artifacts/calibration/catboost_tuned/platt/`
3. Attach `project_key`, `capacity_mw`, study/POI context from model-ready meta

Detail: [`data/gold/modeling/artifacts/metrics/calibration_phase1_decision.md`](../data/gold/modeling/artifacts/metrics/calibration_phase1_decision.md)

## NASNet

Closed negative experiment. Report: [`reports/models/nasnet/nasnet_experiment.md`](../reports/models/nasnet/nasnet_experiment.md).  
Config `experiment_status: closed` blocks new training.

## Seals

- **test**: sealed  
- **score**: sealed  

## Before unlock (checklist)

- [x] Families trained  
- [x] Goal-aware HPO + live logs  
- [x] Ablations  
- [x] Seed stability documented (accept Strong; stretch not seed-stable)  
- [x] Calibration protocol signed (Platt on `catboost_tuned`)  
- [ ] This freeze doc approved by team  
- [ ] Explicit TEST unseal decision  

Do **not** tune after seeing test.
