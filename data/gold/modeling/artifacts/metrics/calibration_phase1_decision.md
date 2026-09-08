# Phase 1 calibration decision (VAL only; TEST sealed)

**Date:** 2026-09-07  
**Deployable model:** `catboost_tuned` (trial-149 hyperparameters, `random_seed=2026`)  
**Selected method:** **Platt** (`best_method_by_cv_brier`)

## Why Platt on `catboost_tuned`

| Model | Best method | CV Brier | CV ECE | CV LogLoss | Raw PR-AUC | Full-val MW@10% |
|-------|-------------|----------|--------|------------|------------|-----------------|
| `catboost_tuned` | **platt** | **0.0385** | 0.0066 | **0.1529** | **0.1213** | **0.291** |
| `catboost_tuned` | isotonic | 0.0385 | **0.0046** | 0.1567 | 0.1213* | 0.328 |
| `catboost_champion_seed_2026` | isotonic | 0.0385 | 0.0065 | 0.1591 | 0.1186 | 0.191 |

\*Isotonic CV PR-AUC drops to ~0.095 on cross-fitted primary; Platt keeps ranking ≈ raw.

Platt wins on primary selection metric (CV Brier), keeps ranking, and improves ECE/log-loss vs raw.

## Protocol for Phase 2

- **Ranking / Precision·Recall·MW Capture@K:** use **raw** `y_prob` from `catboost_tuned` (or top-K from raw scores).
- **Scenario weights / calibrated \(P(W)\):** use **Platt**-calibrated probabilities from  
  `artifacts/calibration/catboost_tuned/platt/`.
- Do **not** re-select models on full-val isotonic fits (overfit risk).

## Artifacts

- Model: `data/gold/modeling/artifacts/models/catboost_tuned/`
- Calibration: `data/gold/modeling/artifacts/calibration/catboost_tuned/`
- Summary: `data/gold/modeling/artifacts/calibration/catboost_tuned/summary.json`
- Run log: `data/gold/modeling/artifacts/metrics/calibration_run.json`
