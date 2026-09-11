# Full-stack demo: CatBoost + Platinum 2 + Platinum 3

Quit scores are **CatBoost** (`catboost_tuned` / trial-149). Not Electrum. Not Platinum 1 delay-months. 2024 stays sealed.

## Scoreboard (code, not gpt-4.1)

| Slot | Value | Honest use |
|------|-------|------------|
| Project | `P::B::E291` · IA Executed · 27.0 MW · 2023-12-31 | Val sample only |
| Scenario | `restudy` | If one additional restudy were on the record. |
| CatBoost P(quit 12m) | 0.07 | Ranking, not a BPM trigger |
| CatBoost under scenario | 0.055 (delta -0.0145) | Sensitivity, not causal |
| Platinum 2 delayed MW now | 25299.4 | EIA planned pile |
| Platinum 2 Holt 3m / 12m | 27748.5 / 37044.3 | History ≤ as-of; not 2024 actuals |
| GIA-matched delayed MW | 0.0 | Thin overlay |
| Risks with BPM index | system_congestion, cod_already_slipped, abandonment, gia_execution, restudy_friction | Procedure units may exist |
| Stub risks | developer_serial_quit | Gaps only; no invented BPM |

## Input

Fixture `platinum4\results\fixtures\full_stack_input.json` loaded `C:\Users\Magjun\Documents\Team-8-XternChallenge-\platinum3\results\sample_cards.json`.

---

## Turn 1 (t1_scoreboard)

searched=True shape=long

# Interconnection procedure note

## 1. Risk Results Track

The CatBoost model estimates a 12-month quit probability of 0.07 for this Interconnection Request (IR), based on the gold freeze (trial-149). This is a ranking score and is not a withdrawal verdict or a BPM-015 duty. Under the Platinum 3 restudy scenario, the model sensitivity shows a delta of -0.0145, meaning the quit probability would decrease if one additional restudy were on the record. This scenario delta is a sensitivity, not a causal law or a procedural trigger.

## 2. System Crowding and Delayed-MW Pile

The Platinum 2 delayed-MW pile, which measures system-wide crowding, is as follows:
- Delayed MW now: 25,299.4 MW
- Delayed MW at 3 months: 27,748.5 MW
- Delayed MW at 12 months: 37,044.3 MW

These figures represent the total EIA-reported planned MW delayed by at least 12 months versus their first-seen date, using a Holt-damped forecast. This is a system stock and does not reflect the Commercial Operation Date (COD) or delay status of this specific IR. The GIA-matched delayed-MW slice for this IR is 0.0 MW, but this overlay is thin and must not be treated as the full list of GIAs. The EIA delayed-MW pile is not a substitute for the actual GIA population.

## 3. Platinum 3 Risks: BPM-015 Index vs Stubs

The following Platinum 3 risks have a corresponding BPM-015 index:
- System congestion (BPM-015 r33 §3.1.1, §4.3)
- COD already slipped (BPM-015 r33 §5.4.6, §7.1)
- Abandonment (BPM-015 r33 §5.4.6, §6.2.11, §4.2.4.6, §5.2.3, §5.2.5, §5.3.3, §5.3.5)
- GIA execution (BPM-015 r33 §7.1)
- Restudy friction (BPM-015 r33 §5.4.6)

The following risks are stubs and do not have a BPM-015 clause in this packet:
- Developer serial quit
- FEMA hazard exposure
- IRA energy-community status

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)
- BPM-015 r33 §6.2.11 - Refunds of Definitive Planning Phase Milestones (M2, M3, M4) (pages 92-95)
- BPM-015 r33 §4.2.4.6 - Refunds of Study Deposits (pages 34-35)
- BPM-015 r33 §3.1.1 - Contour Map (pages 21-22)
- BPM-015 r33 §5.2.5 - Withdrawal from DPP Phase I (pages 50-50)
- BPM-015 r33 §4.3 - Determination of Project Linkages and Potential Grouping (pages 35-35)
- BPM-015 r33 §5.3.5 - Withdrawal from DPP Phase II (pages 52-52)
- BPM-015 r33 §5.3.3 - Interconnection Customer Decision Point II (pages 51-51)
- BPM-015 r33 §5.2.3 - Interconnection Customer Decision Point I (pages 48-48)
- BPM-015 r33 §7.1 - Suspension (pages 126-127)

## Gaps
- developer_serial_quit has no BPM-015 clause
- hazard_exposure has no BPM-015 clause
- policy_incentive has no BPM-015 clause

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

Compliance: not_determined.

---

## Turn 2 (t2_restudy_bpm)

searched=False shape=long

# Interconnection procedure note

## Situation
This inquiry concerns the BPM-015 r33 restudy process when MISO determines that a restudy is required because a peer interconnection request (IR) in the same Definitive Planning Phase (DPP) cycle has withdrawn before all Generator Interconnection Agreements (GIAs), Facilities Construction Agreements (FCAs), and/or Multi-Party Facilities Construction Agreements (MPFCAs) for that cycle have been executed or filed unexecuted with FERC. The CatBoost and Platinum 2/3 risk and crowding figures are context only and do not create or modify BPM-015 duties. This note restates the BPM-015 r33 restudy workflow, funding, and deadlines. It does not treat the CatBoost scenario delta as a procedural deadline and does not invent a serial-quit clause.

## Workflow

If MISO determines that a restudy of any Interconnection Study is required because an IR withdraws or is deemed withdrawn before all GIAs, FCAs, and/or MPFCAs for the DPP cycle have been executed or filed unexecuted with FERC, MISO shall provide notice of a restudy as necessary (BPM-015 r33 §5.4.6). The notice will include a preliminary analysis supporting the need for restudy, an explanation of why restudy is required, and a good faith estimate of the cost to perform the restudy.

The Interconnection Customer (IC) shall notify MISO within five (5) Business Days whether it wishes to proceed with the restudy or withdraw its IR. If the IC fails to notify MISO within this deadline, MISO will deem the IR withdrawn (BPM-015 r33 §5.4.6).

MISO will use reasonable efforts to complete the restudy within sixty (60) Calendar Days from the date of the restudy notice.

## Stakeholders

- MISO (Transmission Provider) shall issue the restudy notice, provide supporting analysis, and estimate costs.
- The Interconnection Customer (IC) shall fund the restudy from the remaining study deposit or from an additional deposit as noticed by MISO. The IC must respond within five (5) Business Days whether to proceed or withdraw.
- The Transmission Owner (TO) coordinates on affected facilities as required by the restudy.

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)

## Gaps
developer_serial_quit has no BPM-015 clause

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score


Compliance: not_determined.

---

## Turn 3 (t3_both_true)

searched=False shape=long

# Interconnection procedure note


## 1. Platinum 2 Crowded Pile (System Crowding) Track

The Platinum 2 delayed-MW pile for this Interconnection Request (IR) is 25,299.4 MW as of the observation date, with Holt projections of 27,748.5 MW at three months and 37,044.3 MW at twelve months. This figure represents system-wide EIA planned delayed MW (delay ≥12 months versus first seen), not the commercial operation date (COD) for this IR. The GIA-matched delayed-MW slice is 0.0 MW for this IR, but this overlay is thin and must not be treated as the full list of Generator Interconnection Agreements (GIAs) in the system. The delayed-MW pile is a measure of system crowding and does not create or modify any BPM-015 duty or deadline.

## 2. Restudy Funding Clock (BPM-015 r33 §5.4.6) Track

If MISO determines that a restudy of an Interconnection Study is required because an interconnection request withdraws or is deemed withdrawn before all GIAs, Facilities Construction Agreements (FCAs), and/or Multi-Party Facilities Construction Agreements (MPFCAs) for that DPP cycle have been executed or filed unexecuted with FERC, MISO shall provide notice of a restudy as necessary. The notice will include a preliminary analysis, an explanation of why restudy is required, and a good faith estimate of the cost to perform the restudy. The Interconnection Customer (IC) shall notify MISO within five (5) Business Days whether it wishes to proceed with the restudy or withdraw the IR. Failure to notify MISO is deemed withdrawal. The IC funds the restudy from the remaining study deposit or from an additional deposit as noticed (BPM-015 r33 §5.4.6).

## 3. Can Both Be True at Once?

Yes, both tracks can be true at once without collapsing system crowding into a BPM-015 restudy trigger. The Platinum 2 delayed-MW pile and the CatBoost quit probability are risk analytics and system context. They do not create, modify, or accelerate the BPM-015 r33 §5.4.6 restudy notice, the five-Business-Day response clock, or the funding obligation. The BPM-015 restudy process is triggered only by the withdrawal or deemed withdrawal of a peer IR in the same DPP cycle, as determined by MISO, not by risk model scores or system crowding overlays.

## 4. Do CatBoost or Serial-Quit Flags Rewrite the BPM-015 Clock or Deposit?

Neither the CatBoost quit score nor the developer serial-quit flag rewrites the five-Business-Day clock or the restudy funding deposit under BPM-015 r33 §5.4.6. These analytics are for risk ranking and scenario sensitivity only. The BPM-015 process and deadlines are set by procedural events (such as peer withdrawal and MISO notice), not by risk model outputs or flags.

## Gaps
- The GIP (Attachment X) is the tariff and is not in this packet.
- developer_serial_quit has no BPM-015 clause

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

Compliance: not_determined.
