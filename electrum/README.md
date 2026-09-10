# Electrum — one notebook per model

Val-only retrains you run **one by one**. Test is sealed. There is **no** shared `electrum/lib.py`; each notebook duplicates a short setup cell.

Locked rules (also in [`data/quality_reports/modeling/retrain_notes.md`](../data/quality_reports/modeling/retrain_notes.md)):

- Train 2020–22 / val 2023 / **test sealed**
- No split shuffle, no 50/50 resampling, no PCA on trees
- Score is **PR-AUC** (chance on val ≈ 0.041). Accuracy is logged on curves only

Batch val-only experiments (already run): `python scripts/run_retrain_ameliorations.py` → [`data/quality_reports/modeling/retrain_val_compare.md`](../data/quality_reports/modeling/retrain_val_compare.md).

## How to run

```text
CPU (Windows):  .\.venv\Scripts\Activate.ps1
                jupyter notebook electrum/<notebook>.ipynb

GPU (CUDA):     .\scripts\wsl-python.cmd -m jupyter notebook electrum/<notebook>.ipynb
                WSL python: /home/magjun/venvs/team8-miso/bin/python
```

Probe both PyTorch and TensorFlow like `scripts/check_cuda.py`. Trees run on CPU. TabM / FT-Transformer / TabPFN use torch CUDA if available. NASNet needs TF GPU via WSL and **warns** (does not silently train for hours on CPU).

Run in order **01 → 11**. Later notebooks do not import earlier ones. After each run, that notebook appends one row to `electrum/results/leaderboard.csv`.

Regenerate notebooks (source of truth for cell text):

```text
python scripts/build_electrum_notebooks.py
```

## Folder layout

```text
electrum/
  README.md
  01_logistic.ipynb … 11_timesfm.ipynb
  results/
    electrum_performance.ipynb   ← val comparison, Plotly
    figures/*.html               ← HTML sidecars from that notebook
    leaderboard.csv
    <model>/{models/, metrics.json, history.csv, plots/}
```

Val comparison (same spirit as [`data/quality_reports/model_performance_report.ipynb`](../data/quality_reports/model_performance_report.ipynb), Plotly instead of matplotlib):

[`results/electrum_performance.ipynb`](results/electrum_performance.ipynb)

Rebuild the report notebook from the leaderboard (no retraining), then re-run it:

```text
python scripts/build_electrum_report.py
jupyter nbconvert --to notebook --execute --inplace electrum/results/electrum_performance.ipynb
```

`history.csv` columns: `step, train_loss, train_acc, val_loss, val_acc` plus `val_pr_auc` when cheap.

## Knobs

Each notebook has one `KNOBS` dict (`SEED`, `USE_CLASS_WEIGHT=False`, maybe `DROP_SPARSE=False`). Defaults match the current champion / `fit_*` recipe. Flip flags for ameliorations; do not add extra notebooks.
