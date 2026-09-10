# BPM-015 tagged procedure index

Current **r33 clean** only (`status: current`, effective 2026-07-01). Not a model. Tags in `ontology.json` are the only allowed values.

| Path | Role |
|------|------|
| `ontology.json` | Closed vocabularies |
| `search_catalog.json` | Shelves, section tree, routes, holes |
| `ontology_graph.json` | Nodes/edges for a later graph |
| `lexical/bm25_idf.json` | BM25 IDF sidecar |
| `dialect/` | BPM register samples for gpt-4.1 |
| `procedures/*.json` | One retrieval atom per subsection |
| `units.jsonl` | Same units, one line each |
| `maps/` | topic, milestone, claim_class (complete); risk_code (seed-only) |
| `packs/README.md` | How Platinum 4 builds a bot packet |

Rebuild: `python scripts/build_miso_policy_index.py`

Do not retrieve r32/redlines unless the as-of date is before 2026-07-01.
