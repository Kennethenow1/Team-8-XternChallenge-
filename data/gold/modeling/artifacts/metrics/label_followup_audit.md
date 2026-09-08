# Label / follow-up audit

Do **not** rebalance validation — keep the real future prevalence.

## Panel by split × year

| split | year | n | withdrawals | withdrawal_rate | complete_followup_rate |
| --- | --- | --- | --- | --- | --- |
| score | 2025 | 1638 | 117 | 0.0714 | 0.1807 |
| score | 2026 | 1038 | 1 | 0.0010 | 0.1590 |
| test | 2024 | 2205 | 922 | 0.4181 | 0.9995 |
| train | 2020 | 580 | 127 | 0.2190 | 1.0000 |
| train | 2021 | 963 | 52 | 0.0540 | 1.0000 |
| train | 2022 | 1734 | 226 | 0.1303 | 1.0000 |
| val | 2023 | 1669 | 69 | 0.0413 | 0.9982 |

## Modeling matrices (`catboost_native_v1`)

- `train` matrix rows=3277, positives=405, rate=0.1236
- `val` matrix rows=1666, positives=69, rate=0.0414
- `test` matrix rows=2204, positives=922, rate=0.4183
- `score` matrix rows=2676, positives=118, rate=0.0441

## 12-month follow-up on validation

- Panel val `complete_followup` rate ≈ **0.9982**
- Rows with `complete_followup=True` are the supervised evaluation population (≥12 months of outcome visibility by construction of the label).
- Modeling val/test matrices are filtered to complete follow-up in feature engineering.

CSV: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/metrics/label_followup_audit.csv`
