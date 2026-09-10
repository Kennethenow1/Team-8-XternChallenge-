# What Platinum 3 is asking

Electrum asks: *will this project quit in about a year?*  
Platinum 1 asked: *how many months will this COD move?* (failed)  
Platinum 2 asks: *how big is the delayed-MW pile later?*

Platinum 3 is not a fourth prediction contest. It asks: **given this project, this date, and this scenario, what risks should a mitigation bot be allowed to say — with numbers we already trust?**

## What goes on the card

| Slot | Source | Honest use |
|------|--------|------------|
| `p_quit_12m` | Electrum CatBoost (freeze `catboost_tuned` if on disk, else the Electrum joblib) | Ranking / calibrated quit risk |
| `pile.delayed_mw_*` | Platinum 2 EIA delayed MW, Holt 3m/12m from history ≤ as-of | System crowding, not this plant’s COD |
| `flags` | Gold as-of facts (GIA, service date already passed, restudy, developer rate, FEMA) | Current state |
| `scenario` + `delta_p_quit` | Same CatBoost on an edited row | Sensitivity (“if this state were true”), not a causal law |
| `risks[]` + `playbook_ids` | Rules on those scores/flags | What Platinum 4 should retrieve from BPM-015 |

Company policy PDFs are **not** trained. Retrieval is **Platinum 4**. Three risks stay stubs (`developer_serial_quit`, `hazard_exposure`, `policy_incentive`).

## Scenarios

`baseline`, `enter_gia`, `already_past_cod`, `restudy`, `rate_shock`, `serial_developer`, `high_system_delay`.

`high_system_delay` does **not** change Electrum features (pile is not a CatBoost column). P(quit) delta is 0; crowding is a separate slot. That is intentional. We already learned that gluing pile into CatBoost is a shallow contest trick.

On 2023 val, **rate_shock** and **serial_developer** raise mean P(quit). **enter_gia**, **already_past_cod**, and **restudy** slightly *lower* it. That is observational CatBoost, not “GIA is safer.” The bot must treat deltas as sensitivities and still surface GIA / already-slipped as **flags**, not as a causal story.

The freeze `catboost_tuned` file is gitignored, so this run scored with the Electrum CatBoost joblib (same trial-149 recipe, no Platt). Drop the freeze model under `data/gold/modeling/artifacts/models/catboost_tuned/` to switch sources.

## What we should not say

- A new model would fix mitigation. It would not.
- Scenario deltas are “if restudy happens, delay = X months.”
- Platinum 1 month-MAE as a bot input.
- EIA delayed MW as the full GIA list.
- 2024 test labels.

## Outputs

`python scripts/run_platinum3_risk_cards.py` writes val cards. `val_card_audit.parquet` has `y_true` for the team. **Do not send that file to ChatGPT.**
