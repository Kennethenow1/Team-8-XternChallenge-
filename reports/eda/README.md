# EDA reports

Exploratory analysis of the point-in-time withdrawal datasets.

| Artifact | Path |
|----------|------|
| Notebook | [`notebooks/eda_pit_withdrawal.ipynb`](../notebooks/eda_pit_withdrawal.ipynb) |
| HTML report | [`eda_report.html`](eda_report.html) |
| Figures | [`figures/`](figures/) |
| Warnings sidecar | [`warnings_summary.md`](warnings_summary.md) |

Rebuild (read-only w.r.t. Gold):

```bash
source .venv/bin/activate
python scripts/run_eda_report.py
```

Does **not** train models or modify `data/gold/`.
