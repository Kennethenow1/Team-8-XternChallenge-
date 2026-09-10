# Platinum 3 — risk-card peripherals

Electrum and Platinum 1/2 trainers are untouched. This track does **not** train another contest model.

It builds the **JSON risk card** a mitigation bot is allowed to see:

- Electrum `P(quit in ~12 months)`
- Platinum 2 delayed-MW pile (now, 3m, 12m Holt from history ≤ as-of)
- Gold facts (GIA, already past COD, developer history, restudy, FEMA, energy community)
- Scenario overlays that **re-score the same CatBoost**
- Playbook ids keyed by risk code

BPM citations (card → procedure units) live in **[Platinum 4](../platinum4/README.md)**.

**Read first:** [WHAT_THESE_RESULTS_MEAN.md](WHAT_THESE_RESULTS_MEAN.md)

| Rule | Value |
|------|--------|
| Question | Given this project, date, and scenario — what risks, with what evidence? |
| Scores | Freeze/Electrum CatBoost + Platinum 2 pile. No new architecture. |
| Val | 2023 cards + scenario sensitivity (diagnostic, not HPO) |
| Test | **2024 sealed** |
| Score | Unlabeled current-queue cards (`--split score`). Not for model picking. |

## Run

```text
python scripts/run_platinum3_risk_cards.py
python scripts/build_platinum3_report.py
jupyter notebook platinum3/01_risk_cards.ipynb
```

Refuse `--split test`. For card → BPM citations: `platinum4/01_bot_packets.ipynb`.

## Layout

```text
platinum3/
  README.md
  WHAT_THESE_RESULTS_MEAN.md
  01_risk_cards.ipynb          ← open this
  results/
    platinum3_risk_cards.ipynb
    schema.json
    playbooks.json
    sample_cards.json
    val_risk_cards.parquet
    val_card_audit.parquet   ← y_true for the team only; not the GPT contract
    scenario_sensitivity.json
```

GPT should ingest `schema.json` + a card from `sample_cards.json`. It must obey `do_not_claim`. Retrieval packets are Platinum 4.

Full `*_risk_cards.jsonl` is regenerated locally (~30MB) and gitignored.
