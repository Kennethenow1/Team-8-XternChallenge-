# Model-ready train — dtype / role readiness

Matrix: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/model_ready_train.parquet`
Rows: **3277** · Columns: **97**

**Verdict:** Ready for `X_train → Model` with **train-only** scaling fitted later (no model fit in this step). Exclude identifier / time_key from `X`.

## Checklist

- [x] Model features are numeric / binary / one-hot / missing indicators
- [x] Label present, binary, 0% missing
- [x] Identifier column(s) present and marked Exclude (`project_key`)
- [x] Time key marked do-not-encode (`observation_date`)
- [x] No leftover columns needing encoding (`encoding_needed=Yes`: 0)
- [x] Nulls kept as null (no zero-fill); features with missing > 0%: **25**

## Role counts

- `numeric`: 49
- `onehot`: 27
- `missing_indicator`: 11
- `binary`: 7
- `identifier`: 1
- `label`: 1
- `time_key`: 1

## Modeling prep rules (A–D)

**A. Scaling** — for logistic / SVM / NN only: standardize continuous `Yes*` columns with
train mean/std. Trees: skip scaling.

**B. Imputation** — sklearn logistic cannot take NaNs. Use **train median** for continuous
NaNs and **keep** `*_missing` / `*_available` indicators. Trees may leave NaNs.
See `logistic_ready_*` / `tree_ready_*` under `data/gold/modeling/`.

**C. Sparse ablation** — features with ≥80% missing (esp. `years_since_last_change`)
are ablation candidates: Model A with / Model B without on **validation**. Do not auto-drop.
See `sparse_feature_flags.md`.

**D. Macros** — low nunique on the annual panel makes r=±1 misleading; keep macros,
do not collapse; see `macro_grain_audit.json`.

## Scaling (detail)

- Continuous numeric columns marked `Yes*`: **49**
- Fit scaler on **train only** for logistic regression / SVM / neural nets.
- Tree models (RF, GBM, etc.) typically do not need scaling.
- One-hot columns already expanded: **27** (`encoding_needed=Already one-hot`).

## Full table

See `model_ready_schema.csv` next to this file.

| feature | dtype | n_unique | missing % | role | encoding | scaling |
|---------|-------|----------|-----------|------|----------|---------|
| `project_key` | str | 1938 | 0.0 | identifier | Exclude | No |
| `observation_date` | datetime64[us] | 3 | 0.0 | time_key | Do not encode blindly | No |
| `withdraw_next_12m` | int64 | 2 | 0.0 | label | No | No |
| `capacity_reduction_pct` | float64 | 24 | 93.226 | numeric | No | Yes* |
| `capacity_reduction_pct_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `cost_change_since_previous_study` | float64 | 96 | 92.402 | numeric | No | Yes* |
| `cost_change_since_previous_study_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `dpp_event_count_to_date` | float64 | 5 | 79.188 | numeric | No | Yes* |
| `dpp_event_count_to_date_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `network_upgrade_cost` | float64 | 225 | 84.803 | numeric | No | Yes* |
| `network_upgrade_cost_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `restudy_count` | float64 | 2 | 89.319 | binary | No | No |
| `study_delay_days` | float64 | 20 | 89.319 | numeric | No | Yes* |
| `upgrade_cost_per_mw` | float64 | 165 | 89.442 | numeric | No | Yes* |
| `upgrade_cost_per_mw_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `extreme_weather_days_12m` | float64 | 20 | 1.068 | numeric | No | Yes* |
| `fema_risk_score` | float64 | 553 | 0.275 | numeric | No | Yes* |
| `population` | float64 | 1231 | 0.275 | numeric | No | Yes* |
| `population_change_since_2020` | float64 | 645 | 0.275 | numeric | No | Yes* |
| `population_yoy_pct` | float64 | 930 | 17.974 | numeric | No | Yes* |
| `population_yoy_pct_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `rural_flag` | float64 | 2 | 0.275 | binary | No | No |
| `storm_events_12m` | float64 | 53 | 1.068 | numeric | No | Yes* |
| `storm_property_damage_12m` | float64 | 338 | 1.068 | numeric | No | Yes* |
| `distance_to_transmission_km` | float64 | 553 | 0.275 | numeric | No | Yes* |
| `mtep_investment_nearby_usd` | float64 | 62 | 0.0 | numeric | No | Yes* |
| `nearby_mtep_upgrade_count` | float64 | 43 | 0.0 | numeric | No | Yes* |
| `nearby_transmission_voltage` | float64 | 9 | 0.275 | numeric | No | Yes* |
| `construction_cost_index_change_12m` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `interest_rate_at_entry` | float64 | 65 | 0.0 | numeric | No | Yes* |
| `interest_rate_at_observation` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `interest_rate_change_since_entry` | float64 | 120 | 0.0 | numeric | No | Yes* |
| `miso_demand_yoy_pct` | float64 | 2 | 17.699 | numeric | No | Yes* |
| `miso_generation_yoy_pct` | float64 | 2 | 17.699 | numeric | No | Yes* |
| `miso_mean_demand_mw` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `miso_net_interchange_mw` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `miso_peak_demand_mw` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `news_count_90d` | float64 | 37 | 0.0 | numeric | No | Yes* |
| `news_sentiment_mean_90d` | float64 | 45 | 0.0 | numeric | No | Yes* |
| `capacity_change_pct` | float64 | 30 | 59.078 | numeric | No | Yes* |
| `capacity_mw` | float64 | 267 | 0.0 | numeric | No | Yes* |
| `developer_active_project_count` | float64 | 54 | 0.0 | numeric | No | Yes* |
| `developer_prior_completion_rate` | float64 | 60 | 0.0 | numeric | No | Yes* |
| `developer_prior_withdrawal_rate` | float64 | 86 | 0.0 | numeric | No | Yes* |
| `is_hybrid` | int64 | 2 | 0.0 | binary | No | No |
| `log1p_capacity_mw` | float64 | 260 | 0.0 | numeric | No | Yes* |
| `months_until_service` | float64 | 535 | 0.305 | numeric | No | Yes* |
| `nearby_queue_mw` | float64 | 113 | 0.0 | numeric | No | Yes* |
| `other_active_mw_same_poi` | float64 | 128 | 0.0 | numeric | No | Yes* |
| `other_active_mw_same_technology` | float64 | 759 | 0.0 | numeric | No | Yes* |
| `other_active_projects_same_poi` | float64 | 8 | 0.0 | numeric | No | Yes* |
| `other_active_projects_same_state` | float64 | 42 | 0.0 | numeric | No | Yes* |
| `prior_12m_withdrawal_count` | int64 | 3 | 0.0 | numeric | No | Yes* |
| `queue_age_months` | float64 | 370 | 0.397 | numeric | No | Yes* |
| `service_date_passed` | int64 | 2 | 0.0 | binary | No | No |
| `service_date_shift_months` | float64 | 12 | 59.078 | numeric | No | Yes* |
| `years_since_last_change` | float64 | 2 | 97.681 | numeric | No | Yes* |
| `years_since_last_change_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `technology_primary__battery` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary__natural_gas` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary__other` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary__solar` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary__wind_onshore` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary__OTHER_RARE` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `technology_primary_missing` | float64 | 1 | 0.0 | missing_indicator | No | No |
| `state_code__AR` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__IA` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__IL` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__IN` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__KY` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__LA` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__MI` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__MN` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__MO` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__MS` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__ND` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__SD` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__TX` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__WI` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code__OTHER_RARE` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `state_code_missing` | float64 | 1 | 0.0 | missing_indicator | No | No |
| `study_phase__In_Progress` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `study_phase__Not_Started` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `study_phase__OTHER_RARE` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `study_phase_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `service_type__ERIS` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `service_type__NRIS` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `service_type__OTHER_RARE` | float64 | 2 | 0.0 | onehot | Already one-hot | No |
| `service_type_missing` | float64 | 2 | 0.0 | missing_indicator | No | No |
| `dpp_delay_info_available` | float64 | 2 | 0.0 | binary | No | No |
| `eia_yoy_available` | float64 | 2 | 0.0 | binary | No | No |
| `project_change_history_available` | float64 | 2 | 0.0 | binary | No | No |
| `avg_withdrawn_mw_12m` | float64 | 3 | 0.0 | numeric | No | Yes* |
| `developer_avg_active_project_mw` | float64 | 122 | 0.0 | numeric | No | Yes* |
| `avg_active_project_mw_state` | float64 | 1261 | 0.031 | numeric | No | Yes* |
| `news_recent_intensity` | float64 | 43 | 0.0 | numeric | No | Yes* |
| `negative_news_share_90d` | float64 | 44 | 0.0 | numeric | No | Yes* |
