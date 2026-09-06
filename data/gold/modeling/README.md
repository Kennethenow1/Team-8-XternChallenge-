# Modeling regularized train set

`train_regularized.parquet` / `.csv` is the train-only numeric feature matrix after
approved collapse transforms (see `data/quality_reports/modeling/feature_engineering_notes.md`).

Built from `withdrawal_panel_enriched` with `split=train` and `complete_followup`.
Does not replace Gold; use this file for modeling experiments.
