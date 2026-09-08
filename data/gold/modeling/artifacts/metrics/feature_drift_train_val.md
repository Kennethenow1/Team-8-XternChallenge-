# Train → validation feature drift

Computed on `catboost_native_v1` (same semantics as foundation_v1).

## Year-grain / macro family (ablation candidates)

These include FRED/EIA macros and system-wide `prior_12m_*` signals.

| feature | train_nunique | val_nunique | smd | ks |
|---------|---------------|-------------|-----|----|
| `miso_demand_yoy_pct` | 2 | 1 | -4.260 | 1.000 |
| `interest_rate_at_observation` | 3 | 1 | 1.665 | 1.000 |
| `miso_generation_yoy_pct` | 2 | 1 | -2.664 | 1.000 |
| `miso_peak_demand_mw` | 3 | 1 | 1.936 | 1.000 |
| `miso_net_interchange_mw` | 3 | 1 | -0.097 | 0.823 |
| `miso_mean_demand_mw` | 3 | 1 | -0.393 | 0.823 |
| `interest_rate_change_since_entry` | 120 | 53 | 1.149 | 0.606 |
| `construction_cost_index_change_12m` | 3 | 1 | -0.721 | 0.529 |
| `prior_12m_withdrawal_count` | 3 | 1 | -0.953 | 0.529 |
| `avg_withdrawn_mw_12m` | 3 | 1 | -1.150 | 0.529 |
| `interest_rate_at_entry` | 65 | 53 | 0.285 | 0.205 |

## Top numeric drift by KS

| feature | smd | ks | train_mean | val_mean |
|---------|-----|----|------------|----------|
| `miso_demand_yoy_pct` | -4.260 | 1.000 | 2.171 | -1.717 |
| `interest_rate_at_observation` | 1.665 | 1.000 | 2.87 | 4.58 |
| `miso_generation_yoy_pct` | -2.664 | 1.000 | 5.252 | -4.108 |
| `miso_peak_demand_mw` | 1.936 | 1.000 | 8.239e+04 | 8.542e+04 |
| `news_count_90d` | -2.110 | 1.000 | 61.39 | 0 |
| `news_sentiment_mean_90d` | 2.701 | 1.000 | -2.003 | 0 |
| `miso_net_interchange_mw` | -0.097 | 0.823 | -2983 | -3080 |
| `miso_mean_demand_mw` | -0.393 | 0.823 | 6.838e+04 | 6.804e+04 |
| `interest_rate_change_since_entry` | 1.149 | 0.606 | 0.6045 | 2.036 |
| `construction_cost_index_change_12m` | -0.721 | 0.529 | 10.98 | -1.365 |
| `prior_12m_withdrawal_count` | -0.953 | 0.529 | 1029 | 437 |
| `avg_withdrawn_mw_12m` | -1.150 | 0.529 | 230.4 | 204.4 |
| `project_change_history_available` | 1.313 | 0.517 | 0.4107 | 0.9274 |
| `queue_age_months` | 0.271 | 0.509 | 23.94 | 34.36 |
| `other_active_mw_same_technology` | 0.116 | 0.375 | 1.251e+05 | 1.346e+05 |

## Largest categorical share shifts

| feature | level | train_share | val_share | delta |
|---------|-------|-------------|-----------|-------|
| `study_phase` | __MISSING__ | 0.823 | 0.000 | -0.823 |
| `study_phase` | System Impact Study | 0.000 | 0.384 | +0.384 |
| `study_phase` | Not Started | 0.074 | 0.349 | +0.275 |
| `study_phase` | IA Executed | 0.001 | 0.187 | +0.186 |
| `service_type` | NRIS | 0.747 | 0.915 | +0.167 |
| `service_type` | __MISSING__ | 0.193 | 0.028 | -0.165 |
| `study_phase` | In Progress | 0.102 | 0.000 | -0.102 |
| `technology_primary` | battery | 0.103 | 0.180 | +0.078 |
| `technology_primary` | solar | 0.717 | 0.658 | -0.058 |
| `study_phase` | Facility Study | 0.000 | 0.043 | +0.043 |
| `study_phase` | Feasibility Study | 0.000 | 0.024 | +0.024 |
| `state_code` | AR | 0.092 | 0.115 | +0.023 |
| `technology_primary` | wind_onshore | 0.120 | 0.097 | -0.023 |
| `state_code` | MI | 0.132 | 0.111 | -0.021 |
| `state_code` | LA | 0.105 | 0.124 | +0.018 |
| `state_code` | IL | 0.124 | 0.137 | +0.014 |
| `state_code` | MS | 0.048 | 0.061 | +0.013 |
| `study_phase` | In Progress (unknown study) | 0.000 | 0.013 | +0.013 |
| `state_code` | WI | 0.092 | 0.082 | -0.011 |
| `state_code` | MN | 0.067 | 0.057 | -0.010 |

CSVs: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/metrics/feature_drift_train_val_numeric.csv`, `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/metrics/feature_drift_train_val_categorical.csv`
