# TimesFM system monthly forecast (rolling-origin)

**System-level branch** (TimesFM-3). Feeds future system conditions; not used alone for project-row model selection.
Target: `withdrawal_count` | folds: 5

| model | RMSE | MAPE |
|-------|------|------|
| naive | 537.4039449055059 | 25.3701556786824 |
| ma3 | 422.41202239835303 | 74.64712438489217 |
| arima | nan | nan |
| timesfm | 477.83889686195647 | 40.52118181968888 |

**TimesFM:** backend=timesfm-3.0

Val-year folds: 1 / 5 (panel grain is annual Dec snapshots).
