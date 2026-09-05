# Status and technology mapping notes

## Status (`src/common/status_map.yaml`)

Canonical `status_clean` values: `active`, `withdrawn`, `completed`, `operational`, `suspended`, `unknown`.

Both `status_raw` and `status_clean` are retained on Silver project rows.

Consistency flags (`status_consistency_flag`):

| Condition | Flag |
|-----------|------|
| Withdrawn + withdrawal date | `confirmed_withdrawal` |
| Withdrawn without date | `withdrawal_uncertain_timing` |
| Active + withdrawal date | `active_withdrawal_conflict` |
| Operational date present | `operational_outcome` |

MISO **Done** → `completed` (not operational) until the official definition is confirmed against MISO documentation.

## Technology (`src/common/technology_map.yaml`)

Ontology: `solar`, `wind_onshore`, `wind_offshore`, `battery`, `natural_gas`, `nuclear`, `hydro`, `other`, `unknown`.

Hybrids use `technology_primary`, `technology_secondary`, `is_hybrid`, `technology_count`, plus component MW columns (`solar_mw`, `wind_mw`, `battery_mw`, `gas_mw`).
