# Top-model feature ablations (validation only)

**Test / score sealed.** All runs on val split only.

Policy: `/home/kenneth-enow/X-intern_misochallenge/Team-8-XternChallenge-/data/gold/modeling/artifacts/feature_policy_v1.json`

## catboost

| ablation | status | pr_auc | roc_auc | brier | log_loss | n_features | note |
|----------|--------|--------|---------|-------|----------|------------|------|
| `v1_full` | ok | 0.08055838553394236 | 0.6983882823772835 | 0.04659927332423008 | 0.2062168159534337 | 64 | Default V1 feature set |
| `v1_minus_macro` | ok | 0.04397544814330087 | 0.5202372201501002 | 0.04856078726436444 | 0.2178345994949774 | 53 | Drop full macro family (FRED + EIA + system-wide) |
| `v1_minus_dpp` | ok | 0.06715915508850871 | 0.6382029711506176 | 0.04606318583818903 | 0.20365334096531942 | 51 | Drop DPP cost/delay/restudy family |
| `v1_plus_years_since_last_change` | ok | 0.07215055631391278 | 0.691364242737742 | 0.04562186103767064 | 0.19687644756437797 | 66 | Add years_since_last_change (+ missing indicator if available) |
| `v1_plus_capacity_mw` | ok | 0.07963994179662921 | 0.690375069196773 | 0.04520339287686292 | 0.19931449794052025 | 65 | Add raw capacity_mw alongside log1p_capacity_mw |
| `v1_minus_macro_fred` | ok | 0.04099363063236985 | 0.4943235958726961 | 0.04883785588335776 | 0.22030908229330995 | 60 | Drop FRED macro columns only |
| `v1_minus_macro_eia` | ok | 0.06840045730718862 | 0.6632272467398111 | 0.04355245022346309 | 0.19218368686713538 | 59 | Drop EIA/MISO macro columns only |
| `v1_minus_macro_system` | ok | 0.09545440625918594 | 0.7325056945541004 | 0.04487259372826071 | 0.19578870156147046 | 62 | Drop system-wide prior_12m_* + avg_withdrawn_mw_12m |

## lightgbm

| ablation | status | pr_auc | roc_auc | brier | log_loss | n_features | note |
|----------|--------|--------|---------|-------|----------|------------|------|
| `v1_full` | ok | 0.045588377079022094 | 0.5371166952528745 | 0.04692720188581686 | 0.21515757796232463 | 85 | Default V1 feature set |
| `v1_minus_macro` | ok | 0.03549163962337559 | 0.41652373562748995 | 0.046537842766276157 | 0.21173148765633945 | 74 | Drop full macro family (FRED + EIA + system-wide) |
| `v1_minus_dpp` | ok | 0.09397894637124066 | 0.7679798172297696 | 0.04585611187884582 | 0.21021538495943026 | 72 | Drop DPP cost/delay/restudy family |
| `v1_plus_years_since_last_change` | ok | 0.04864623239493728 | 0.5666875391358798 | 0.0467353585154408 | 0.21429065334876835 | 87 | Add years_since_last_change (+ missing indicator if available) |
| `v1_plus_capacity_mw` | ok | 0.04633500836101629 | 0.5483243037216521 | 0.04664522309294905 | 0.213899853917008 | 86 | Add raw capacity_mw alongside log1p_capacity_mw |
| `v1_minus_macro_fred` | ok | 0.04372856665491106 | 0.5168204876897806 | 0.046576212128181506 | 0.21356626930984096 | 81 | Drop FRED macro columns only |
| `v1_minus_macro_eia` | ok | 0.09496742273525356 | 0.7517355911900031 | 0.046245449770741534 | 0.21206802684109172 | 80 | Drop EIA/MISO macro columns only |
| `v1_minus_macro_system` | ok | 0.04598288465243355 | 0.542071637944334 | 0.04665323132189948 | 0.21393725846600573 | 83 | Drop system-wide prior_12m_* + avg_withdrawn_mw_12m |
