# Platinum — COD delay models

**Read first if the scoreboard is confusing:** [WHAT_THESE_RESULTS_MEAN.md](WHAT_THESE_RESULTS_MEAN.md)

Val-only retrains that predict **how many months a project's commercial-operation date will slip**, not `withdraw_next_12m`. Electrum / the withdrawal freeze are untouched.

Headline: **MAE** of `cod_slip_months_next_12m`. Companion: PR-AUC of `cod_slip_ge_12m`.

## Locked rules

- Train 2020–22 / val 2023 / **test sealed**
- No split shuffle, no SMOTE, no PCA on trees
- Follow-up window is **24 months** because Berkeley **2024** vintages have empty service dates. Last-known COD as of `t` is the PIT feature; future COD in `(t, t+24m]` is the label.
- MISO `operational_date` is **Appl In Service Date**, not proven COD. EIA-860M is the independent planned-COD check when it matches.
- We are **not** claiming a mature MISO Firm Service Step-Up failure record. The process is still proposed. These models quantify generator execution risk a future Step-Up increment would revalidate.

## How to run

```text
python scripts/run_delay_gold.py          # EIA-860M + FERC-730 probe + gold + matrices
python scripts/audit_cod_delay_labels.py
python scripts/build_platinum_notebooks.py
python scripts/build_platinum_report.py

CPU:  .\.venv\Scripts\Activate.ps1
      jupyter notebook platinum/01_logistic.ipynb
GPU:  .\scripts\wsl-python.cmd -m jupyter notebook platinum/09_seq_cnn.ipynb
```

Run **01 → 12**. Each notebook appends `platinum/results/leaderboard.csv`.

HPO (val MAE):

```text
python scripts/run_platinum_hpo.py --family catboost --trials 20
```

## Folder layout

```text
platinum/
  README.md
  01_logistic.ipynb … 12_timesfm.ipynb
  results/<model>/{metrics.json, history.csv, models/, plots/}
```

`09_seq_cnn` is the delay-native CNN (`MAX_EPOCHS=100`, `MIN_EPOCHS_BEFORE_STOP=8`).
`10_nasnet_cnn` uses [`configs/nasnet_delay.yaml`](../configs/nasnet_delay.yaml): 100 frozen + 20 finetune, GPU required, Huber head. There is **no** `MAX_EPOCHS=2` override.

If `data/gold/delay/split_manifest.json` has `neural_nets_ok: false` (val labeled < 200), TabM / FT-T / NASNet skip with `insufficient_n`.

## Risks

- Label sparsity of true in-service dates; GIQ COD *revisions* are the main label
- 2024 Berkeley COD hole forces a 24-month follow-up (documented in gold delay README)
- NASNet-as-image remains a weak hypothesis
- FERC-730 skipped — no clean bulk table; no transmission CatBoost notebook
