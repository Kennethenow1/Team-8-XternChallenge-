# What Platinum 4 is asking

Platinum 3 built the **risk card**. Platinum 4 asks: **given that card and/or a question, which BPM-015 clauses should the bot actually read, and how should gpt-4.1 restate them?**

Not a fifth prediction contest. Not months of COD slip. Not a FERC compliance score.

## What goes in the packet

| Slot | Source | Honest use |
|------|--------|------------|
| `card` | Platinum 3 (2023 val samples) | Project, phase, flags, risks |
| `gold_stack` | CatBoost P(quit) + Platinum 2 pile + Platinum 3 scenario | Numbers as context, not BPM duties |
| `query` | Free text + requirements | Audience, dialect, `need` (optional `diagram`) |
| `retrieved[]` | Hybrid search, cap 8–12 | Clauses that govern delay / restudy / withdrawal / GIA |
| `search_trace` | Named algorithms + directives | Provenance: where the bot looked |
| `graph_slice` | Slice of `ontology_graph.json` | Units and tags that actually fired |
| `gaps` | Planner | Stub risks, coverage misses, zero hits |
| `compliance` | Always `not_determined` | We do not score a COD slip as compliant |
| `do_not_claim` | Copied from the risk card | Same bans as Platinum 3 |

Quit probability is **CatBoost** (`catboost_tuned` / trial-149). Not Electrum. Not Platinum 1 delay-months. The pile is Platinum 2 Holt on EIA delayed MW. Scenario deltas stay sensitivities.

Three risks have **no BPM clause**: `developer_serial_quit`, `hazard_exposure`, `policy_incentive`. Those stay stub playbooks. Do not invent a MISO rule.

## Composer

The planner is a short gpt-4.1 JSON call: does history already have the clause, or do we search? Short ask vs full note vs citations vs diagram. Then one write call. Code post-check is not a model pass. Follow-ups reuse held BPM units from `platinum4/results/sessions/default.json`.

## What we should not say

- A 12th model would fix mitigation.
- Retrieved text means the project is FERC-compliant or non-compliant.
- Platinum 1 month-MAE as a bot input.
- 2024 test labels (still sealed; packets are val samples only).

## Outputs

`python scripts/build_miso_policy_index.py` writes the catalog, graph, maps, and `platinum4/results/sample_bot_packets.json`.

`python scripts/run_platinum4_answer.py` writes `platinum4/results/answers/<slug>.md` and `.json`.

Open `02_full_stack_playground.ipynb` to read the saved CatBoost-stack notes and type your own follow-ups. `python scripts/run_platinum4_full_stack.py` writes `platinum4/results/answers/full_stack_conversation.md`. Open `01_bot_packets.ipynb` for catalog shelves, the ontology table, search_trace, and the composed note. `python scripts/serve_platinum4_ui.py` serves a briefing UI at `http://127.0.0.1:8765/` (note + mermaid on the left, chat on the right). **Do not send `val_card_audit.parquet` (y_true) to ChatGPT.**
