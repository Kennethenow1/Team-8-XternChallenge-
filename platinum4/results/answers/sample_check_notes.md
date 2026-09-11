# restudy_funding

Question: Who funds a restudy if a peer withdraws?

# Interconnection procedure note

## Situation

You asked who funds a restudy if a peer Interconnection Request (IR) withdraws. This restates BPM-015 r33 and is not a legal opinion.

## Workflow

If MISO (the Transmission Provider) determines that a restudy is required due to a peer IR withdrawal before all Generator Interconnection Agreements (GIAs) are executed or filed, MISO shall provide notice of the restudy, including a good faith estimate of the cost to perform the restudy (BPM-015 r33 §5.4.6). The Interconnection Customer (IC) shall notify MISO within five (5) Business Days whether it wishes to proceed with the restudy or withdraw its own IR. The cost to perform the restudy is funded from any remaining study deposit or by an additional deposit as specified in the restudy notice (BPM-015 r33 §5.4.6).

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

# restudy_followup

Question: Who pays for that, and how many Business Days does the IC have to answer?

MISO (the Transmission Provider) will provide a good faith estimate of the cost to perform the Interconnection Study restudy, and the Interconnection Customer (IC) is responsible for funding the restudy as noticed. The IC must notify MISO within five (5) Business Days whether it wishes to proceed with the restudy or withdraw its interconnection request (IR) (BPM-015 r33 §5.4.6).

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)


## Gaps
No additional planner gaps were recorded.

Compliance: not_determined.

---

# decision_point_ii

Question: What happens at Decision Point II?

# Interconnection procedure note

## 1. Risk results

- CatBoost P(quit 12m): 0.898. This is a ranking score, not a BPM trigger and not a withdrawal verdict.
- Platinum 2 delayed MW (system crowding): 25,299.4 MW (EIA planned pile + Holt). This is not this IR's Commercial Operation Date (COD).
- The GIA-matched delayed-MW slice is a thin overlay and does not represent the full GIA pile.
- Flags (high_quit_risk, cod_already_slipped, pile_crowded) are current as-of facts. They do not create BPM duties by themselves.

## 2. Interconnection procedure note

### Situation
You asked what happens at Decision Point II in the MISO generator interconnection process. This restates BPM-015 r33. It is not a legal opinion.

### Workflow
After MISO delivers the revised System Impact Study (SIS) and Affected System analysis, the Interconnection Customer (IC) enters Decision Point II. The IC shall have fifteen (15) Business Days to decide whether to proceed to Definitive Planning Phase III (DPP III) or withdraw its interconnection request (IR) (BPM-015 r33 §5.3.3). During Decision Point II, the IC may reduce the size of its IR by up to ten percent (10%), but the Milestone (M4) calculation will be based on the DPP II results. If the IC chooses to proceed, it must pay the DPP III Milestone (M4) before the end of Decision Point II (BPM-015 r33 §5.3.3). If MISO does not receive written confirmation from the IC by the deadline, MISO shall deem the IR withdrawn and refund the DPP II Milestone (M3) and any remaining study deposits (BPM-015 r33 §5.3.5).

### Citations
- BPM-015 r33 §5.3.3 - Interconnection Customer Decision Point II (page 51)
- BPM-015 r33 §5.3.5 - Withdrawal from DPP Phase II (page 52)

### Gaps
- The Generator Interconnection Procedures (GIP) and Attachment X are referenced for deposit rules but are not included in this packet.

### Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

## Gaps
The GIP (Attachment X) is the tariff and is not in this packet.

## Citations
- BPM-015 r33 §5.3.3 - Interconnection Customer Decision Point II (pages 51-51)
- BPM-015 r33 §5.3.5 - Withdrawal from DPP Phase II (pages 52-52)

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

Compliance: not_determined.

---

# gia_cod_delay

Question: What delay clauses apply after GIA when COD has already passed?

# Interconnection procedure note

## 1. Risk results

- CatBoost P(quit 12m): 0.07. This is a ranking score, not a BPM-015 trigger or a withdrawal verdict.
- Platinum 2 delayed MW (system-wide, not this IR): 25,299.4 MW delayed ≥12 months as of 2023-12-31. This is system crowding, not this project's Commercial Operation Date (COD).
- The GIA-matched delayed-MW overlay is thin and does not represent the full GIA pile.
- Scenario delta is a sensitivity, not a causal law.
- Flags (e.g., COD already slipped, developer serial) are current facts but do not create BPM-015 duties by themselves.

## 2. BPM-015 delay clauses after GIA and after COD

### Situation

You asked what delay clauses apply after the Generator Interconnection Agreement (GIA) is executed and the Commercial Operation Date (COD) has already passed. This restates BPM-015 r33. This is not a legal opinion.

### Workflow

If the Interconnection Customer (IC) is delayed after GIA execution, the IC may request to amend GIA milestones, but this requires the consent of MISO and the Transmission Owner (TO) under the terms of the effective GIA. The IC must provide a written statement from a company officer describing the circumstances, reach written agreement with the TO on specific milestone changes, and demonstrate that the change will not significantly harm other queued projects. MISO will review the request and determine whether to consent to the amendment.

If the IC achieves Commercial Operation, the IC must notify MISO and the TO within thirty (30) Calendar Days using Appendix E to the GIA and provide as-built modeling data.

If the IC seeks to suspend construction after GIA execution, suspension is only permitted for Force Majeure reasons and requires an up-front payment (BPM-015 r33 §7.1).

### Citations

 The Platinum 3 flags do not create a BPM-015 delay duty.
 The Platinum 3 flags do not create a BPM-015 delay duty.
- BPM-015 r33 §7.1 - Suspension (pages 126-127)

### Gaps

- There is no BPM-015 clause for developer_serial_quit.
- The GIP (tariff) is not in this packet; GIA Article 30.10 is referenced but not provided here.

### Must not claim

- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

## Citations
- BPM-015 r33 §7.1 - Suspension (pages 126-127)

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

## Gaps
developer_serial_quit has no BPM-015 clause

Compliance: not_determined.

---

# d2_deposit

Question: What is the DPP Study Funding Deposit D2?

# Interconnection procedure note

## Situation

You asked what the DPP Study Funding Deposit D2 is. This restates BPM-015 r33 and is not a legal opinion.

## Workflow

The Interconnection Customer (IC) must pay the DPP Study Funding Deposit (D2) before entering the Definitive Planning Phase (DPP). The amount of the D2 deposit depends on the project’s MW size, as shown in Table 4-1 of BPM-015 r33. If the IC is required by a state regulatory body to take two Points of Interconnection (POIs) through the study process, the IC must submit study deposits for each POI. Failure to pay the D2 deposit will result in withdrawal of the interconnection request (IR) (BPM-015 r33 §4.2.4.5).

## Citations
- BPM-015 r33 §4.2.4.5 - DPP Study Funding Deposit (D2) (pages 33-34)

## Gaps
- The BPM does not specify the exact process for refunding the D2 deposit after withdrawal; see related sections for refund rules.
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
