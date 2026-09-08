# Evaluation protocol (Phase 1)

Fixed temporal splits only. Do not use random CV.

- train_years: [2020, 2021, 2022]
- validation_year: 2023
- test_year: 2024

**Selection split: `val`.** Splits `['score', 'test']` are sealed until the architecture is frozen.

Primary metrics: PR-AUC, ROC-AUC, Brier, ECE, LogLoss.
Operational: Precision@5/10%, Recall@10%, Lift@10%, Withdrawn-MW-Capture@10%.
HPO objective: PR-AUC with Brier/ECE/LogLoss tie-break.
Tree early stopping: LogLoss.

Sanity on **val**: no-skill PR-AUC ≈ **val** prevalence (~0.041), not train (~0.124).

See `docs/model_architecture.md` and `docs/modeling_experiment_protocol.md`.
