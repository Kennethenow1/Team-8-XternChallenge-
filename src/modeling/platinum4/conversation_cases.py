"""Paragraph-length conversation cases: card overlay + BPM, two-track analysis."""

from __future__ import annotations

TURNS: list[dict[str, object]] = [
    {
        "id": "t1_card_plus_restudy",
        "need": ["workflow", "stakeholders", "citations", "do_not_claim"],
        "question": (
            "I am looking at the Platinum 3 risk card for this IR: IA Executed, planned COD already "
            "passed, delayed-MW pile crowded, and developer serial quit is flagged. A peer in the "
            "same DPP cycle has withdrawn, so I need two tracks in one note, not a slogan. First, "
            "read the card as risk context only: what those flags do and do not authorize you to "
            "claim. Second, walk the BPM-015 r33 restudy path if MISO restudies because that peer "
            "left before all GIAs/FCAs/MPFCAs for the cycle were executed or filed unexecuted: who "
            "notices, who funds the restudy from remaining deposit or additional deposit, and the "
            "Interconnection Customer deadline. Do not treat p(quit) or pile crowding as a BPM duty. "
            "Do not invent a serial-quit clause."
        ),
    },
    {
        "id": "t2_inline_clock",
        "need": ["workflow", "citations", "do_not_claim"],
        "question": (
            "Stay on that last restudy track. I still need the IC response clock and who actually "
            "puts up the money, in enough detail to sit beside the card's restudy_friction flag. "
            "How many Business Days does the IC have after the notice, what happens if they stay "
            "silent, and does the serial-quit flag change any of that funding or timing. Quote "
            "only what you already held unless a clause is missing."
        ),
    },
    {
        "id": "t3_d2_vs_restudy",
        "need": ["workflow", "citations", "do_not_claim"],
        "question": (
            "Combine two deposit analyses for this same IR. Track A is the restudy funding you "
            "already described. Track B is the DPP Study Funding Deposit D2 if the IC withdraws "
            "instead of proceeding. I need both in one note: when D2 is refunded less actual study "
            "cost versus at risk, and whether a restudy notice after a peer withdrawal uses D2, a "
            "remaining study deposit, or a separate additional deposit as noticed. Do not collapse "
            "D2 into a parent refund section if §4.2.4.5 is in the packet. Then tell me whether "
            "those two tracks can both be true at once for an IA-executed project."
        ),
    },
    {
        "id": "t4_site_control_overlay",
        "need": ["workflow", "citations", "do_not_claim", "diagram"],
        "question": (
            "Keep the restudy and D2 tracks in history. Now overlay a third analysis: site control "
            "for this same IR. The card is already IA Executed, so site control may be a prior-phase "
            "duty. I need you to compare (1) the site-control demonstration and timing in BPM-015 r33 "
            "with (2) the restudy notice path from the last notes, and say whether missing site control "
            "rewrites the restudy funding or the five-Business-Day clock. Include a procedure map of "
            "who acts if a peer withdrawal restudy notice and a site-control gap are both on the desk. "
            "If FEMA hazard or IRA energy-community on a sister card would change either track, say so "
            "or put the hole under Gaps."
        ),
    },
    {
        "id": "t5_gip_cod_card",
        "need": ["workflow", "citations", "do_not_claim"],
        "question": (
            "From the last notes, combine tariff posture with post-GIA delay for this same executed "
            "GIA. The card says COD has already passed. If the IC misses the restudy-notice window, "
            "BPM-015 r33 treats that as deemed withdrawal of the IR and points at Section 3.6 of the "
            "GIP. I need both analyses without merging them into one fake rule: (1) what the held "
            "restudy unit actually says versus what Attachment X would have to supply, and (2) "
            "whether §7.3 still governs IC delay / milestone amendment on this executed GIA because COD "
            "has slipped. Do not infer that the GIA is void. Do not quote months of future COD slip. "
            "If the GIP is not in the packet, keep it in Gaps and still restudy versus §7.3 as two "
            "tracks."
        ),
    },
]


def questions() -> list[str]:
    return [str(t["question"]) for t in TURNS]
