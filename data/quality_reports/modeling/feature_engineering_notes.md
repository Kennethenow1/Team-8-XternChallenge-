# Feature engineering notes

Train-only engineered **model-ready** matrix (collapsed/derived features — not statistical regularization).
Gold/Silver unchanged.

## Applied transforms

- **queue_age**: Keep queue_age_months; drop years_in_queue
- **poi_congestion**: Keep other_active_projects_same_poi; drop same_poi_project_count
- **prior_withdrawals**: Keep count; add avg_withdrawn_mw_12m; drop prior_12m_withdrawn_mw
- **developer_scale**: Keep developer_active_project_count; add developer_avg_active_project_mw; drop total MW
- **state_pressure**: Keep other_active_projects_same_state; add avg_active_project_mw_state; drop other_active_mw_same_state
- **news**: Keep news_count_90d; add news_recent_intensity + negative_news_share_90d; drop N30 and Nneg counts
- **dpp_missingness**: Collapse to dpp_delay_info_available; keep restudy_count and study_delay_days values
- **eia_yoy_missingness**: Collapse to eia_yoy_available; keep YoY values
- **capacity_service_missingness**: Collapsed to project_change_history_available
- **macro**: NOT collapsed — see macro_grain_audit.json
- **study_service_missing**: Kept both — see study_service_missing_audit.json

## Dropped from engineered matrix

- `years_in_queue`
- `same_poi_project_count`
- `prior_12m_withdrawn_mw`
- `developer_total_active_mw`
- `other_active_mw_same_state`
- `news_count_30d`
- `negative_news_count_90d`
- `restudy_count_missing`
- `study_delay_days_missing`
- `miso_demand_yoy_pct_missing`
- `miso_generation_yoy_pct_missing`
- `capacity_change_pct_missing`
- `service_date_shift_months_missing`

## Derived columns

- `avg_withdrawn_mw_12m`
- `developer_avg_active_project_mw`
- `avg_active_project_mw_state`
- `news_recent_intensity`
- `negative_news_share_90d`

## Macro audit (not collapsed)

- Recommendation: `keep_macros_as_is`
- Warning: Annual Gold repeats a few year-level macro values across thousands of projects; project-row Pearson correlations are misleading. Prefer native year_month grain.
- Panel train nunique: `{"interest_rate_at_observation": 3, "interest_rate_at_entry": 65, "interest_rate_change_since_entry": 120, "construction_cost_index_change_12m": 3, "miso_mean_demand_mw": 3, "miso_peak_demand_mw": 3, "miso_demand_yoy_pct": 2, "miso_generation_yoy_pct": 2, "miso_net_interchange_mw": 3}`
- Train observation-year rows: 3

## Study/service missingness (kept both)

- Recommendation: `keep_both_pending_audit`
- Pearson(missing indicators): -0.9496285520086469
- Agreement: 0.01556301495270064; complement: 0.9844369850472994

Model-ready train file: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/model_ready_train.parquet`
Engineered parquet (report mirror): `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/quality_reports/modeling/train_numeric_engineered.parquet`
Schema / readiness: `model_ready_schema.csv`, `model_ready_readiness.md`
