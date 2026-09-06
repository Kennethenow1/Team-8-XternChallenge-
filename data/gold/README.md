# Gold — modeling tables

**What Gold is:** analysis-ready panels. Each training row is a project at an **observation date**, with a label (where allowed) and covariates. External features are joined **point-in-time** from Silver.

**What Gold is not:** raw downloads (Bronze) or unjoined enrichment inventory (Silver).

## What lives here

| Artifact | Function | Use for |
|----------|----------|---------|
| `annual_withdrawal_training/` | Yearly classification rows + `withdraw_next_12m` | Base labeled training (queue covariates only) |
| `survival_training/` | `(start, stop]` survival intervals | Time-to-withdraw / competing risks |
| `current_miso_scoring/` | Active MISO projects, **no future labels** | Scoring / deployment candidates |
| `withdrawal_panel_enriched.parquet` | Annual panel + all usable enrichment | ★ Full feature table for research |
| `current_miso_scoring_enriched.parquet` | Same joins for live queue | Score today’s projects |
| `modeling/model_ready_train.parquet` | Train-only engineered numeric matrix | ★ **Live matrix for model experiments** |
| `split_manifest.json` | train / val / test / score years | Leakage-safe time split |

Base tables are **directories**; enriched panels are **flat** parquet(+csv) next to them. That is intentional (older builders vs enrichment writer) — see [`../../docs/data_layout.md`](../../docs/data_layout.md).

## Labels vs features

| Column / concept | Role |
|------------------|------|
| `withdraw_next_12m` | Binary label (historical panels only) |
| `complete_followup` | Whether the 12-month window is fully observed |
| `split` | train / val / test / score |
| Queue + enrichment columns | Predictors (never use future info) |

## Feature families on the enriched panel (by prediction role)

| Role | Example columns |
|------|-----------------|
| Queue friction | `queue_age_months`, `study_phase`, `capacity_mw`, `months_until_service` |
| Study / cost | `network_upgrade_cost`, `study_delay_days`, `restudy_count` |
| Grid / POI | `other_active_projects_same_poi`, `distance_to_transmission_km`, `nearby_mtep_upgrade_count` |
| Developer | `developer_prior_withdrawal_rate`, `developer_active_project_count` |
| Local / policy | `population`, `fema_risk_score`, `energy_community_eligible`, storm counts |
| Macro | `interest_rate_at_observation`, `miso_demand_yoy_pct`, … |
| News | `news_count_90d`, `news_sentiment_mean_90d` (engineered: intensity / negativity share) |

Engineering notes: `../quality_reports/modeling/feature_engineering_notes.md`.

Modeling folder detail: [`modeling/README.md`](modeling/README.md).
