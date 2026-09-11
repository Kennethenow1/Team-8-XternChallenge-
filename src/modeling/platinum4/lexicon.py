"""Closed phrase table: question text -> ontology tags. GPT does not assign tags."""

from __future__ import annotations

import re
PHRASES: list[tuple[str, dict[str, list[str]]]] = [
    (r"\brestud(y|ies)\b", {"topic": ["restudy"], "risk_code": ["restudy_friction"]}),
    (r"\bdecision point ii\b|\bdp[\s-]?ii\b|\bdecision point 2\b", {"topic": ["decision_point"], "milestone": ["M4"]}),
    (r"\bdecision point i\b|\bdp[\s-]?i\b|\bdecision point\b", {"topic": ["decision_point"]}),
    (r"\bwithdraw(n|al|s)?\b|\bdeemed withdraw", {"topic": ["withdrawal"], "risk_code": ["abandonment"]}),
    (r"\bgia\b|\binterconnection agreement\b|\bia executed\b|\bia pending\b", {"topic": ["gia_negotiation"], "gi_phase": ["gia"]}),
    (
        r"\bcod delay\b|\bcommercial operation\b|\bin-service date\b|\bservice date\b",
        {"topic": ["commercial_operation"], "risk_code": ["cod_already_slipped"]},
    ),
    (r"\bM1\b|\bapplication milestone", {"milestone": ["M1"]}),
    (r"\bM2\b", {"milestone": ["M2"]}),
    (r"\bM3\b", {"milestone": ["M3"]}),
    (r"\bM4\b", {"milestone": ["M4"]}),
    (r"\bD1\b|\bapplication fee\b", {"milestone": ["D1"]}),
    (r"\bD2\b|\bstudy funding\b|\bstudy funding deposit\b|\bdpp study funding", {"milestone": ["D2"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure"]}),
    (r"\bletter of credit\b|\brefund", {"topic": ["deposit_refund"]}),
    (r"\bnetwork upgrade\b|\bcost allocation\b", {"topic": ["cost_allocation"], "risk_code": ["cost_pressure"]}),
    (r"\bcontour\b|\bgrouping\b", {"topic": ["scoping"], "risk_code": ["system_congestion"]}),
    (r"\bsite control\b", {"topic": ["site_control"]}),
    (r"\bpost-?gia\b|\bsuspension\b|\bforce majeure\b", {"gi_phase": ["post_gia"]}),
    (r"\bserial quit\b|\bdeveloper serial", {"risk_code": ["developer_serial_quit"]}),
    (r"\bFEMA\b|\bhazard exposure\b", {"risk_code": ["hazard_exposure"]}),
    (r"\bIRA\b|\benergy[- ]community", {"risk_code": ["policy_incentive"]}),
    (
        r"\brisk card\b|\bp\(quit\)|\bquit probability\b|\bdelayed[- ]mw\b|\bqueue pile\b|\bcrowd(ed|ing)\b",
        {"risk_code": ["system_congestion"]},
    ),
]


def extract_tags(question: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        "gi_phase": [],
        "topic": [],
        "risk_code": [],
        "milestone": [],
        "claim_class": [],
        "actor": [],
    }
    blob = question or ""
    for pat, tags in PHRASES:
        if re.search(pat, blob, re.I):
            for k, vals in tags.items():
                for v in vals:
                    if v not in out[k]:
                        out[k].append(v)
    return {k: v for k, v in out.items() if v}


def merge_tag_sets(*sets: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for s in sets:
        for k, vals in (s or {}).items():
            merged.setdefault(k, [])
            for v in vals:
                if v not in merged[k]:
                    merged[k].append(v)
    return merged
