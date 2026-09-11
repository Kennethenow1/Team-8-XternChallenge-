# Interconnection procedure note

## 1. Restudy after Peer Withdrawal

If MISO determines that a restudy of an Interconnection Study is required because an interconnection request (IR) withdraws or is deemed withdrawn before all Generator Interconnection Agreements (GIAs), Facilities Construction Agreements (FCAs), and/or Multi-Party Facilities Construction Agreements (MPFCAs) for the DPP cycle have been executed or filed unexecuted with FERC, MISO shall provide notice of a restudy as necessary. The notice will include a preliminary analysis, an explanation of why restudy is required, and a good faith estimate of the cost to perform the restudy. The Interconnection Customer (IC) shall notify MISO within five (5) Business Days whether it wishes to proceed with the restudy or withdraw its IR. Failure to notify MISO is deemed withdrawal. The IC funds the restudy from the remaining study deposit or from an additional deposit as noticed (BPM-015 r33 §5.4.6).

## 2. Post-GIA Delay and Commercial Operation

Once the GIA is executed and the planned Commercial Operation Date (COD) has already passed, the IC must provide notification to MISO and the Transmission Owner (TO) after the project achieves commercial operation. This notification must be received by MISO within thirty (30) Calendar Days of the actual COD and should include as-built modeling data. If the IC requests to amend GIA milestones due to delay, such amendments require the consent of all parties (MISO, TO, and IC) under Article 30.10 of the GIA. The IC must provide a written statement describing the circumstances, reach agreement with the TO, and demonstrate no significant harm to other queued projects before MISO will consider the amendment (BPM-015 r33 §7.7, §7.3).

## 3. Alternate Path: Decision Point II Withdrawal and Deposits

If the IC were still at Decision Point II, the following would apply:
- The IC may withdraw its IR during Decision Point II, which lasts fifteen (15) Business Days after delivery of the revised System Impact Study (SIS) and Affected System analysis. If the IC withdraws before the end of Decision Point II, it is eligible for a one hundred percent (100%) refund of the DPP II Milestone (M3). If the IC proceeds to DPP III, it must pay the DPP III Milestone (M4) before the end of Decision Point II. If the IR is withdrawn after Decision Point II, the M3 and M4 deposits become at risk and are used to fund Network Upgrades. The DPP Study Funding Deposit (D2) is refunded, less actual study costs, if withdrawal occurs by the end of Decision Point I; after that, D2 is at risk (BPM-015 r33 §5.3.3, §6.2.11, §4.2.4.5).

## 4. Stub Risks: Developer Serial Quit, FEMA Hazard, IRA Energy-Community

There is no clause in BPM-015 r33 that changes any duty or procedure based on developer serial quit, county FEMA hazard, or IRA energy-community status. These factors do not alter the BPM-015 process (see Gaps).

---

## Procedure map

```mermaid
flowchart TD
    peerWithdraws["Peer IR withdraws before all GIAs/FCAs/MPFCAs executed"]
    misoNotice["MISO issues restudy notice with analysis and cost estimate"]
    icDecision["IC notifies MISO within 5 Business Days to proceed or withdraw"]
    icFunds["IC funds restudy from remaining or additional deposit"]
    misoRestudy["MISO performs restudy"]
    toCoord["TO coordinates on affected facilities if applicable"]

    peerWithdraws --> misoNotice
    misoNotice --> icDecision
    icDecision -->|Proceed| icFunds
    icFunds --> misoRestudy
    misoRestudy --> toCoord
    icDecision -->|Withdraw| end["IR withdrawn"]
```

This diagram shows the workflow after a peer IR withdraws before all agreements are executed. MISO issues a restudy notice, the IC has five (5) Business Days to decide whether to proceed or withdraw, and if proceeding, the IC funds the restudy. MISO then performs the restudy, coordinating with the TO as needed.

---

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)
- BPM-015 r33 §7.7 - Commercial Operation (pages 129-130)
- BPM-015 r33 §6.2.11 - Refunds of Definitive Planning Phase Milestones (M2, M3, M4) (pages 92-95)
- BPM-015 r33 §5.3.3 - Interconnection Customer Decision Point II (pages 51-51)
- BPM-015 r33 §4.2.4.5 - DPP Study Funding Deposit (D2) (pages 33-34)
- BPM-015 r33 §7.3 - Interconnection Customer delays (pages 128-129)

## Gaps
- The GIP (Attachment X) is the tariff and is not in this packet.
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

# Follow-up

# Interconnection procedure note

## 1. Deemed Withdrawal of the Interconnection Request

If the Interconnection Customer (IC) fails to respond to MISO’s restudy notice within five (5) Business Days, MISO shall deem the interconnection request (IR) withdrawn (BPM-015 r33 §5.4.6). The BPM states that failure to notify MISO to proceed with the restudy is treated as withdrawal of the IR. The BPM references the GIP for the process but does not provide the GIP text in this packet.

## 2. Applicability of Post-GIA IC Delay Clause

The post-GIA Interconnection Customer delay clause in BPM-015 r33 §7.3 applies to requests to amend Generator Interconnection Agreement (GIA) milestones after execution of the GIA. However, if the IR is deemed withdrawn under the restudy process, the BPM does not specify whether the GIA remains in effect or is terminated as a result. The effect on the GIA and continued applicability of §7.3 after deemed withdrawal is not addressed in the retrieved BPM-015 r33 units. The GIP (Attachment X) is the controlling tariff and is not in this packet.

## Citations
- BPM-015 r33 §5.4.6 - Interconnection Study Restudy (pages 56-56)
- BPM-015 r33 §7.3 - Interconnection Customer delays (pages 128-129)

## Gaps
The GIP (Attachment X) is the tariff and is not in this packet.

## Must not claim
- do not quote months of future COD slip as a model output
- do not claim a MISO Step-Up / Firm Service failure record
- do not treat EIA delayed MW as a complete GIA list (overlay is thin)
- do not treat scenario deltas as causal effects
- do not use FERC-730 as a clean delay source
- do not unseal 2024 test labels or tune on test/score

Compliance: not_determined.
