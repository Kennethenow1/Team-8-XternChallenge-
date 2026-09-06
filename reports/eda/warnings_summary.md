# EDA data-quality and leakage warnings

- **high**: Score/partial splits have incomplete 12m follow-up; do not treat label rates there as supervised truth.
  - evidence: `[{"split": "score", "n": 2676, "complete_followup_rate": 0.17227204783258596, "label_rate": 0.044095665171898356}, {"split": "test", "n": 2205, "complete_followup_rate": 0.999546485260771, "label_rate": 0.418140589569161}, {"split": "train", "n": 3277, "complete_followup_rate": 1.0, "label_rate": 0.1235886481537992}, {"split": "val", "n": 1669, "complete_followup_rate": 0.9982025164769323, "label_`
- **critical**: Outcome / label columns present on panel — never use as features.
  - evidence: `["withdraw_next_12m", "next_outcome", "complete_followup"]`
- **high**: prior_12m_withdrawal_count is effectively system/year-grain (not project-local).
  - evidence: `{"unique_values_per_train_year": {"2020": 1, "2021": 1, "2022": 1}}`
- **medium**: DPP upgrade costs are sparse; missingness is informative — do not zero-fill.
  - evidence: `{"network_upgrade_cost_nonnull_rate": 0.10298158135748448}`
- **medium**: years_since_last_change is very sparse on train (policy v1 drops it).
  - evidence: `{"train_nonnull_rate": 0.023191943851083308}`
- **low**: Map coordinates are mostly county centroids, not site GPS — treat geo plots as approximate.
  - evidence: `{"county_centroid": 5419, "null": 189}`
- **high**: Enrichment leakage audit has rows with available_date after observation_date (see quality report).
  - evidence: `{"n_flagged_rows": 80468, "top_sources": {"weather_county_month": 37092, "developer_quarter": 27048, "county_year": 10321, "study_events": 4018, "policy_state_date": 1989}}`
- **medium**: Some panel rows flagged never_in_training (current MISO / non-Berkeley lineage).
  - evidence: `{"false": 7578, "true": 2249}`
