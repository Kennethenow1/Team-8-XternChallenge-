# Platinum 2 — delayed MW in GIA next year

Electrum and `platinum/` are untouched. This track forecasts **how many delayed megawatts** are sitting in the planned inventory, not how many months one project will slip.

**Read first:** [WHAT_THESE_RESULTS_MEAN.md](WHAT_THESE_RESULTS_MEAN.md)

| Rule | Value |
|------|--------|
| Target | `delayed_mw` (EIA planned stock, delay ≥12 months vs first seen) |
| Overlay | `gia_delayed_mw` (fuzzy GIQ match × GIA as-of t) |
| Headline | 12-month-ahead RMSE vs seasonal naive |
| Sanity | 3-month-ahead RMSE |
| Val | target year ≤ 2023 |
| Test | **2024 sealed** |

## Run

```text
python scripts/run_platinum2_gold.py
python scripts/build_platinum2_notebooks.py
python scripts/build_platinum2_report.py
python scripts/run_platinum2_all.py
```

TimesFM: WSL GPU, last in the runner.

```text
wsl -d Ubuntu -e bash -lc "cd /mnt/c/Users/Magjun/Documents/Team-8-XternChallenge- && PYTHONPATH=. /home/magjun/venvs/team8-miso/bin/python -u scripts/run_platinum2_all.py"
```

## Layout

```text
platinum2/
  01_seasonal_naive.ipynb … 07_timesfm.ipynb
  results/<model>/{metrics.json, history.csv, plots/}
  results/leaderboard.csv
```

This is EIA planned-COD slip stock in MISO-footprint states. It is **not** a MISO Step-Up failure record.
