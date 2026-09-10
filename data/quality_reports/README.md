# Quality reports

Not training data — diagnostics and coverage written by the pipeline.

| Item | Contents |
|------|----------|
| [`model_performance_report.ipynb`](model_performance_report.ipynb) | VAL tournament comparison: matplotlib charts, metric meanings, observations |
| Electrum family report | [`../../electrum/results/electrum_performance.ipynb`](../../electrum/results/electrum_performance.ipynb) — Plotly charts over `electrum/results/` |
| `modeling/figures/` | PNGs written by that notebook |
| `enrichment/` | Coverage HTML/JSON, harvest summaries, leakage checks |
| `modeling/` | Feature inventory, corr preview, engineering notes, macro audit |
| [`modeling/retrain_notes.md`](modeling/retrain_notes.md) | Locked retrain rules: no PCA on trees, no split shuffle, no 50/50, test sealed |
| [`modeling/retrain_val_compare.md`](modeling/retrain_val_compare.md) | Val-only amelioration comparison vs unrotated CatBoost |
| [`modeling/pls_pca_val_ablation.md`](modeling/pls_pca_val_ablation.md) | Logistic current vs train-only PLS vs PCA-90% negative control |

**Live modeling matrix** is not here — use `../gold/modeling/model_ready_train.parquet`.
**Fitted scores** live in `../gold/modeling/artifacts/metrics/`. Test/score remain sealed.
