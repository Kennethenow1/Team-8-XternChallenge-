# Feature policy V1 (logistic / tree default X)

Default `X` columns: **85** (from 94 model-ready features).

## Default drops

- `capacity_mw`
- `technology_primary_missing`
- `state_code_missing`
- `years_since_last_change`
- `years_since_last_change_missing`
- `technology_primary__OTHER_RARE`
- `state_code__OTHER_RARE`
- `study_phase__In_Progress`
- `service_type__NRIS`

## Reference dummies dropped (dummy trap)

- `technology_primary` → drop `technology_primary__OTHER_RARE`
- `state_code` → drop `state_code__OTHER_RARE`
- `study_phase` → drop `study_phase__In_Progress`
- `service_type` → drop `service_type__NRIS`

## Ablation packs

### `ablation_years_since_last_change`
- Action: `add_to_v1`
- Note: Default excluded (~97.7% missing). Model A = V1+these; Model B = V1.
- Columns (2): `years_since_last_change`, `years_since_last_change_missing`

### `ablation_dpp_family`
- Action: `remove_from_v1`
- Note: Keep in V1 by default; ablate entire DPP cost/delay/restudy family.
- Columns (13): `capacity_reduction_pct`, `capacity_reduction_pct_missing`, `cost_change_since_previous_study`, `cost_change_since_previous_study_missing`, `dpp_event_count_to_date`, `dpp_event_count_to_date_missing`, `network_upgrade_cost`, `network_upgrade_cost_missing`, `restudy_count`, `study_delay_days`, `upgrade_cost_per_mw`, `upgrade_cost_per_mw_missing`, `dpp_delay_info_available`

### `ablation_macro_family`
- Action: `remove_from_v1`
- Note: Includes FRED/EIA macros and system-wide prior_12m_* year-grain signals.
- Columns (11): `construction_cost_index_change_12m`, `interest_rate_at_entry`, `interest_rate_at_observation`, `interest_rate_change_since_entry`, `miso_demand_yoy_pct`, `miso_generation_yoy_pct`, `miso_mean_demand_mw`, `miso_net_interchange_mw`, `miso_peak_demand_mw`, `prior_12m_withdrawal_count`, `avg_withdrawn_mw_12m`

### `ablation_with_capacity_mw`
- Action: `add_to_v1`
- Note: Sanity: V1 uses log1p_capacity_mw only; add raw capacity_mw back if needed.
- Columns (1): `capacity_mw`


## Verification notes

- **restudy_count**: Among non-null train values only {0,1} appear (mostly 0). Effectively an 'any restudy in eligible DPP history' flag, not a rich multi-restudy count.
- **nearby_transmission_voltage**: Nine discrete kV classes (115–765). Ordered discrete; OK as numeric continuous proxy.
- **prior_12m_withdrawal_count**: Only 3 unique values on train (= observation years). Built in build_training.py as system-wide queue withdrawals in (t-12m, t], not project-local. Year-grain market signal; included in ablation_macro_family.
- **avg_withdrawn_mw_12m**: Derived as prior_12m_withdrawn_mw / prior_12m_withdrawal_count; inherits same 3-year grain.
- **onehot_reference**: Dropped one reference dummy per categorical group for unregularized logistic (refs: {'technology_primary': 'technology_primary__OTHER_RARE', 'state_code': 'state_code__OTHER_RARE', 'study_phase': 'study_phase__In_Progress', 'service_type': 'service_type__NRIS'}).

Artifacts: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/feature_policy_v1.json`, `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/feature_columns_v1.json`
