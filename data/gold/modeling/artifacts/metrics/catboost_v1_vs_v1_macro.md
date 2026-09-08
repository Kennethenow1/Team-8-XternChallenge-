# CatBoost V1 vs V1−Macro

Same default CatBoost settings; early stop on val LogLoss.
Macros dropped in V1−Macro (11): `construction_cost_index_change_12m`, `interest_rate_at_entry`, `interest_rate_at_observation`, `interest_rate_change_since_entry`, `miso_demand_yoy_pct`, `miso_generation_yoy_pct`, `miso_mean_demand_mw`, `miso_net_interchange_mw`, `miso_peak_demand_mw`, `prior_12m_withdrawal_count`, `avg_withdrawn_mw_12m`.

**HPO feature set:** `v1`

| metric | V1 | V1−Macro |
|--------|----|----------|
| `pr_auc` | 0.08055838553394236 | 0.04397544814330087 |
| `roc_auc` | 0.6983882823772835 | 0.5202372201501002 |
| `brier` | 0.04659927332423008 | 0.04856078726436444 |
| `ece` | 0.07995720983753875 | 0.08665516828425093 |
| `log_loss` | 0.2062168159534337 | 0.2178345994949774 |
| `precision_at_5pct` | 0.047619047619047616 | 0.03571428571428571 |
| `precision_at_10pct` | 0.10778443113772455 | 0.05389221556886228 |
| `recall_at_10pct` | 0.2608695652173913 | 0.13043478260869565 |
| `lift_at_10pct` | 2.602447279354335 | 1.3012236396771675 |
| `withdrawn_mw_capture_at_10pct` | 0.22366007744039126 | 0.09374363154676991 |
| `best_iteration` | 308 | 149 |
| `n_features` | 64 | 53 |

Choice artifact: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/metrics/catboost_hpo_feature_set.json`
