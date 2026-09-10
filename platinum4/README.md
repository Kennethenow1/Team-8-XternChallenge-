# Platinum 4 — retrieval catalog, hybrid search, gpt-4.1 notes

Electrum and Platinum 1/2/3 trainers are untouched. This track does **not** train a model.

It takes a **Platinum 3 risk card and/or a free-text question**, finds tagged BPM-015 r33 units, and asks **gpt-4.1** to write a procedure note in the BPM dialect. Tags and the search planner are the source of truth. No vector DB in this pass. No silent fallback to another chat model.

**Read first:** [WHAT_THESE_RESULTS_MEAN.md](WHAT_THESE_RESULTS_MEAN.md)

| Rule | Value |
|------|--------|
| Input | Card and/or question (`query.v1`) |
| Index | `docs/miso_policy/index/` (BPM-015 r33 clean only) |
| Catalog | `search_catalog.json`, `ontology_graph.json` |
| Search | Named algorithms + directives; `search_trace` on every packet |
| Composer | **gpt-4.1** only — two LLM passes (plan, write) plus a code post-check |
| Compliance | Always `not_determined` |
| Test | **2024 sealed** |

## Run

```text
python scripts/run_platinum3_risk_cards.py
python scripts/build_miso_policy_index.py
python scripts/run_platinum4_answer.py --question "Who funds a restudy if a peer withdraws?" --project-key P::B::E291 --reset-session
python scripts/run_platinum4_answer.py --question "Who pays for that?"
python scripts/build_platinum4_report.py
jupyter notebook platinum4/01_bot_packets.ipynb
```

Only the three val sample projects (`P::B::E291`, `P::J2280`, `P::J2460`). Do not batch the full val set. Do not pass `--split test`.

`OPENAI_API_KEY` lives in gitignored `.env`. If it is missing, the CLI still writes a template skeleton and runs the code post-check.

## Layout

```text
platinum4/
  README.md
  WHAT_THESE_RESULTS_MEAN.md
  01_bot_packets.ipynb
  results/
    sample_bot_packets.json
    answers/<slug>.md
    answers/<slug>.json
```

Policy index: [`docs/miso_policy/index/`](../docs/miso_policy/index/). Dialect pack: [`docs/miso_policy/index/dialect/`](../docs/miso_policy/index/dialect/).
