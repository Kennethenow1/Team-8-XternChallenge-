# Map hand-check (Platinum 3 risk codes)

Canonical `risk_code → unit_ids` are **seed clauses**, not every descendant tagged by a chapter prefix. Retrieval still scores all procedure units by tag overlap.

| risk_code | BPM-015 r33 | Notes |
|-----------|-------------|--------|
| `abandonment` | §5.2.5, §5.3.5, §4.2.4.6, §6.2.11, §5.2.3, §5.3.3 | Withdrawal / Decision Point I–II / milestone refunds |
| `restudy_friction` | §5.4.6 | Interconnection Study Restudy (deposit / LoC draw is in §4.2.4) |
| `cod_already_slipped` | §4.2 (screening), §7.3, §7.7 | COD rules in screening + post-GIA IC delay. **Not** Platinum 1 months |
| `gia_execution` | §6.2.7, §6.2.8, §6.2.9, §7.3, §7.7 | GIA negotiation / filing / post-GIA |
| `system_congestion` | §3.1.1, §4.3 | Contour map / grouping — **workflow context**, not this plant’s COD |
| `cost_pressure` | §4.2.4.5 (D2), §4.2.4, §6.2.3 | D2 table and NU cost — not PSS/E methods |
| `developer_serial_quit` | **none** | Stub playbook only. Do not invent a MISO rule |
| `hazard_exposure` | **none** | FEMA is gold context, not BPM |
| `policy_incentive` | **none** | IRA / energy-community is not a BPM clause |

GIQ `study_phase` is coarser than DPP 1/2/3. See `gi_phase_to_units.json`.

`topic_to_units.json`, `milestone_to_units.json`, and `claim_class_to_units.json` are **complete inverted maps** of tagged units. The risk-code map stays **seed-only** (this table).
