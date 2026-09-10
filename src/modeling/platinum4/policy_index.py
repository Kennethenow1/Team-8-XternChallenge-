"""BPM-015 tagged procedure index: ontology, subsection split, rule tags.

Platinum 4. Not a model. Current r33 clean only. Tags are closed lists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.common.paths import REPO_ROOT
from src.modeling.platinum3.schema import RISK_CODES  # closed list; P4 does not invent codes

POLICY_ROOT = REPO_ROOT / "docs" / "miso_policy"
INDEX_DIR = POLICY_ROOT / "index"
PROCEDURE_DIR = INDEX_DIR / "procedures"
MAP_DIR = INDEX_DIR / "maps"
FULL_MD = POLICY_ROOT / "extracted" / "bpm-015-r33-clean" / "FULL.md"

SCHEMA_VERSION = "policy_index.v1"
DOC_ID = "bpm-015-r33-clean"
PDF_NAME = "01_bpm-015-r33_generator_interconnection_clean.pdf"
EFFECTIVE = "2026-07-01"

GI_PHASES = (
    "pre_queue",
    "application_review",
    "dpp1",
    "dpp2",
    "dpp3",
    "gia",
    "post_gia",
    "eras",
    "der_afs",
)
MILESTONES = ("M1", "M2", "M3", "M4", "D1", "D2")
ACTORS = ("ic", "miso", "to", "affected_system", "ferc", "lse", "neighboring_rto")
TOPICS = (
    "site_control",
    "withdrawal",
    "restudy",
    "deposit_refund",
    "delay_of_study",
    "gia_negotiation",
    "cost_allocation",
    "deliverability",
    "transfer_of_ownership",
    "commercial_operation",
    "scoping",
    "decision_point",
)
CLAIM_CLASSES = (
    "workflow",
    "timeline_target",
    "deposit_rule",
    "study_method",
    "do_not_use_as_legal_opinion",
)

# BPM subsection prefixes -> tags (longest prefix wins).
PREFIX_RULES: list[tuple[str, dict[str, list[str]]]] = [
    ("5.4.6", {"gi_phase": ["dpp3"], "topic": ["restudy", "delay_of_study"], "risk_code": ["restudy_friction", "abandonment"], "claim_class": ["workflow", "timeline_target"], "actor": ["ic", "miso", "to"]}),
    ("5.2.5", {"gi_phase": ["dpp1"], "topic": ["withdrawal"], "risk_code": ["abandonment"], "claim_class": ["workflow", "deposit_rule"], "actor": ["ic", "miso"], "milestone": ["M2", "M3"]}),
    ("5.3.5", {"gi_phase": ["dpp2"], "topic": ["withdrawal"], "risk_code": ["abandonment"], "claim_class": ["workflow", "deposit_rule"], "actor": ["ic", "miso"], "milestone": ["M3", "M4"]}),
    ("5.2.3", {"gi_phase": ["dpp1"], "topic": ["decision_point"], "risk_code": ["abandonment"], "claim_class": ["workflow"], "actor": ["ic", "miso"], "milestone": ["M3"]}),
    ("5.3.3", {"gi_phase": ["dpp2"], "topic": ["decision_point"], "risk_code": ["abandonment"], "claim_class": ["workflow"], "actor": ["ic", "miso"], "milestone": ["M4"]}),
    ("5.2.4", {"gi_phase": ["dpp1"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure", "abandonment"], "claim_class": ["deposit_rule"], "actor": ["ic", "miso"], "milestone": ["M3"]}),
    ("5.3.4", {"gi_phase": ["dpp2"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure", "abandonment"], "claim_class": ["deposit_rule"], "actor": ["ic", "miso"], "milestone": ["M4"]}),
    ("5.2.2", {"gi_phase": ["dpp1"], "topic": ["delay_of_study"], "claim_class": ["timeline_target", "workflow"], "actor": ["ic", "miso"]}),
    ("5.3.2", {"gi_phase": ["dpp2"], "topic": ["delay_of_study"], "claim_class": ["timeline_target", "workflow"], "actor": ["ic", "miso"]}),
    ("5.4.2", {"gi_phase": ["dpp3"], "topic": ["delay_of_study"], "claim_class": ["timeline_target", "workflow"], "actor": ["ic", "miso"]}),
    ("5.4.4", {"gi_phase": ["dpp3"], "topic": ["delay_of_study", "gia_negotiation"], "claim_class": ["timeline_target", "workflow"], "actor": ["ic", "miso"]}),
    ("5.1.2", {"gi_phase": ["dpp1"], "topic": ["site_control"], "risk_code": ["abandonment"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("5.5", {"gi_phase": ["dpp3", "gia"], "topic": ["transfer_of_ownership"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("5.2", {"gi_phase": ["dpp1"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("5.3", {"gi_phase": ["dpp2"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("5.4", {"gi_phase": ["dpp3"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("5.1", {"gi_phase": ["dpp1"], "topic": ["site_control"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("4.2.1", {"gi_phase": ["application_review"], "milestone": ["M1"], "topic": ["scoping"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("4.2.2", {"gi_phase": ["application_review", "dpp1"], "milestone": ["M2"], "topic": ["deposit_refund"], "risk_code": ["abandonment", "cost_pressure"], "claim_class": ["deposit_rule", "workflow"], "actor": ["ic", "miso"]}),
    ("4.2.3", {"gi_phase": ["application_review"], "topic": ["deposit_refund"], "claim_class": ["deposit_rule"], "actor": ["ic", "miso"]}),
    ("4.2.4.4", {"gi_phase": ["application_review"], "milestone": ["D1"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure"], "claim_class": ["deposit_rule"], "actor": ["ic", "miso"]}),
    ("4.2.4.5", {"gi_phase": ["application_review"], "milestone": ["D2"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure"], "claim_class": ["deposit_rule"], "actor": ["ic", "miso"]}),
    ("4.2.4.6", {"gi_phase": ["application_review", "dpp1"], "topic": ["withdrawal", "deposit_refund"], "risk_code": ["abandonment"], "claim_class": ["deposit_rule", "workflow"], "actor": ["ic", "miso"], "milestone": ["M2", "D2"]}),
    ("4.2.4", {"gi_phase": ["application_review"], "topic": ["deposit_refund"], "risk_code": ["cost_pressure"], "claim_class": ["deposit_rule", "workflow"], "actor": ["ic", "miso"]}),
    ("4.2", {"gi_phase": ["application_review"], "topic": ["commercial_operation"], "risk_code": ["cod_already_slipped"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("4.1", {"gi_phase": ["application_review"], "topic": ["scoping"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to", "affected_system"]}),
    ("4.3", {"gi_phase": ["application_review"], "topic": ["cost_allocation"], "risk_code": ["system_congestion"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("3.1.1", {"gi_phase": ["pre_queue"], "topic": ["scoping"], "risk_code": ["system_congestion"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("3.3", {"gi_phase": ["pre_queue"], "topic": ["scoping"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("6.2.11", {"gi_phase": ["dpp1", "dpp2", "dpp3"], "topic": ["withdrawal", "deposit_refund"], "risk_code": ["abandonment"], "claim_class": ["deposit_rule", "workflow"], "actor": ["ic", "miso"], "milestone": ["M2", "M3", "M4"]}),
    ("6.2.9", {"gi_phase": ["gia"], "topic": ["gia_negotiation"], "risk_code": ["gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("6.2.7", {"gi_phase": ["gia"], "topic": ["gia_negotiation"], "risk_code": ["gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("6.2.8", {"gi_phase": ["gia"], "topic": ["gia_negotiation"], "risk_code": ["gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to", "ferc"]}),
    ("6.2", {"gi_phase": ["dpp3", "gia"], "topic": ["gia_negotiation", "cost_allocation"], "risk_code": ["cost_pressure", "gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("6.1", {"gi_phase": ["dpp1", "dpp2", "dpp3"], "topic": ["cost_allocation", "deliverability"], "claim_class": ["study_method"], "actor": ["ic", "miso", "to"]}),
    ("6.3", {"gi_phase": ["dpp1", "dpp2", "dpp3"], "actor": ["miso", "neighboring_rto", "affected_system"], "claim_class": ["workflow"], "topic": ["delay_of_study"]}),
    ("6.4", {"gi_phase": ["dpp1", "dpp2", "dpp3"], "actor": ["miso", "neighboring_rto", "affected_system"], "claim_class": ["workflow"], "topic": ["delay_of_study"]}),
    ("7.3", {"gi_phase": ["post_gia"], "topic": ["delay_of_study"], "risk_code": ["cod_already_slipped", "gia_execution"], "claim_class": ["workflow", "timeline_target"], "actor": ["ic", "miso", "to"]}),
    ("7.7", {"gi_phase": ["post_gia"], "topic": ["commercial_operation"], "risk_code": ["cod_already_slipped", "gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("7.1", {"gi_phase": ["post_gia"], "topic": ["delay_of_study"], "risk_code": ["gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("4.5", {"gi_phase": ["application_review"], "actor": ["miso", "to", "lse"], "claim_class": ["workflow"], "topic": ["scoping"]}),
    ("8", {"gi_phase": ["der_afs"], "actor": ["miso", "to", "affected_system"], "claim_class": ["workflow", "study_method"]}),
    ("9", {"gi_phase": ["eras"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("7", {"gi_phase": ["post_gia", "gia"], "topic": ["gia_negotiation", "commercial_operation"], "risk_code": ["gia_execution"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("5", {"gi_phase": ["dpp1", "dpp2", "dpp3"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("4", {"gi_phase": ["application_review"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("3", {"gi_phase": ["pre_queue"], "topic": ["scoping"], "claim_class": ["workflow"], "actor": ["ic", "miso", "to"]}),
    ("2", {"gi_phase": ["pre_queue", "application_review", "dpp1"], "claim_class": ["workflow"], "actor": ["ic", "miso"]}),
    ("1", {"claim_class": ["do_not_use_as_legal_opinion", "workflow"], "actor": ["miso"]}),
]

KEYWORD_TOPIC = [
    (r"\bsite control\b", "site_control"),
    (r"\bwithdraw", "withdrawal"),
    (r"\brestudy\b", "restudy"),
    (r"\brefund|\bdeposit\b|\bletter of credit\b", "deposit_refund"),
    (r"\bdecision point\b", "decision_point"),
    (r"\bdelay", "delay_of_study"),
    (r"\bcost allocation\b|\bnetwork upgrade", "cost_allocation"),
    (r"\bdeliverability\b|\bNRIS\b|\bERIS\b", "deliverability"),
    (r"\btransfer of ownership\b", "transfer_of_ownership"),
    (r"\bcommercial operation\b|\bCOD\b", "commercial_operation"),
    (r"\bscoping meeting\b", "scoping"),
    (r"\bGIA\b|\binterconnection agreement\b", "gia_negotiation"),
]
KEYWORD_MILESTONE = [
    (r"\bM1\b|\bMilestone \(M1\)", "M1"),
    (r"\bM2\b", "M2"),
    (r"\bM3\b", "M3"),
    (r"\bM4\b", "M4"),
    (r"\bD1\b|\bApplication Fee", "D1"),
    (r"\bD2\b|\bStudy Funding", "D2"),
]
KEYWORD_ACTOR = [
    (r"\bInterconnection Customer\b|\b\bIC\b", "ic"),
    (r"\bMISO\b|\bTransmission Provider\b", "miso"),
    (r"\bTransmission Owner\b|\b\bTO\b", "to"),
    (r"\bAffected System\b", "affected_system"),
    (r"\bFERC\b", "ferc"),
    (r"\bLoad Serving\b|\bLSE\b", "lse"),
    (r"\bPJM\b|\bSPP\b|\bManitoba\b|\bMinnkota\b", "neighboring_rto"),
]

# Explicit seeds so the nine Platinum 3 risk codes are honest (empty = no BPM clause).
RISK_SEED_SECTIONS = {
    "abandonment": ["5.2.5", "5.3.5", "4.2.4.6", "6.2.11", "5.2.3", "5.3.3"],
    "restudy_friction": ["5.4.6"],
    "cod_already_slipped": ["4.2", "7.3", "7.7"],
    "gia_execution": ["6.2.7", "6.2.8", "6.2.9", "7.3", "7.7"],
    "system_congestion": ["3.1.1", "4.3"],
    "cost_pressure": ["4.2.4.5", "4.2.4", "6.2.3"],
    "developer_serial_quit": [],
    "hazard_exposure": [],
    "policy_incentive": [],
}

STUB_RISKS = ("developer_serial_quit", "hazard_exposure", "policy_incentive")
PROTECTED_SECTIONS = {p for p, _ in PREFIX_RULES} | {s for seeds in RISK_SEED_SECTIONS.values() for s in seeds}

# Messy subsections: do not inherit parent risk tags.
TAG_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "5.2.3.1": {"claim_class": ["study_method"], "risk_code": [], "topic": []},
    "6.2.9.1": {"claim_class": ["study_method"]},
    "6.2.1": {"claim_class": ["study_method"], "risk_code": []},
}

IMPACT_BY_ACTOR = {
    "ic": "Interconnection Customer: milestones, deposits, withdrawal, restudy funding, site control, GIA execution.",
    "miso": "MISO (Transmission Provider): study cycles, notices, restudies, GIA filing.",
    "to": "Transmission Owner: scoping, facilities, local criteria, construction.",
    "affected_system": "Affected System / neighboring TO: coordination and restudy of impacts.",
    "ferc": "FERC: GIA filing / unexecuted filing; not a compliance score on this card.",
    "lse": "Load-serving entity: reliability criteria coordination where FAC-002 / Attachment FF apply.",
    "neighboring_rto": "Neighboring RTO (PJM/SPP/MH): affected-system studies and limits.",
}

PAGE_RE = re.compile(r"^## Page (\d+)\s*$")
HEAD_NUM = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s*$")
HEAD_INLINE = re.compile(r"^(\d+(?:\.\d+){1,3})\.?\s+([A-Z][A-Za-z0-9][\w .,/()'’\-]{0,90})$")
APP_RE = re.compile(r"^Appendix\s+([A-Z])\b(.*)$", re.I)

BODY_START_PAGE = 18
MIN_CHARS = 280
MAX_CHARS = 12000


def ontology() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": DOC_ID,
        "effective_date": EFFECTIVE,
        "gi_phase": list(GI_PHASES),
        "milestone": list(MILESTONES),
        "actor": list(ACTORS),
        "topic": list(TOPICS),
        "risk_code": list(RISK_CODES),
        "claim_class": list(CLAIM_CLASSES),
        "stub_risks_no_bpm": list(STUB_RISKS),
        "note": "Closed vocabularies. GPT must not invent tags. Tariff (Attachment X) still controls if it conflicts with BPM-015.",
    }


def _title_ok(title: str) -> bool:
    t = title.strip()
    if not t or len(t) > 95:
        return False
    if len(t.split()) > 16:
        return False
    if "shall" in t.lower() or t.lower().startswith("except "):
        return False
    return t[0].isalpha() or t[0] in "“\"'"


def _num_ok(num: str) -> bool:
    """BPM-015 body chapters are 1–9. Reject years (2024.) and list debris."""
    if num.startswith("app."):
        return True
    if num == "0":
        return False
    head = num.split(".", 1)[0]
    if not head.isdigit():
        return False
    return 1 <= int(head) <= 9


def _depth(num: str) -> int:
    return num.count(".") + 1


def parse_full_md(path: Path | None = None) -> list[dict[str, Any]]:
    """Return ordered heading spans from FULL.md (r33 clean)."""
    text = (path or FULL_MD).read_text(encoding="utf-8")
    # drop YAML front matter
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    lines = text.splitlines()
    page = 1
    heads: list[dict[str, Any]] = []
    records: list[tuple[int, str]] = []
    for ln in lines:
        m = PAGE_RE.match(ln.strip())
        if m:
            page = int(m.group(1))
            continue
        records.append((page, ln))

    def add_head(i: int, num: str, title: str) -> None:
        pg = records[i][0]
        if not _num_ok(num):
            return
        if num.endswith(".0"):
            return
        heads.append({"i": i, "num": num, "title": title.strip(), "page": pg})

    for i, (pg, ln) in enumerate(records):
        s = ln.strip()
        if not s:
            continue
        a = APP_RE.match(s)
        if a and pg >= 140:
            letter = a.group(1).upper()
            rest = (a.group(2) or "").strip(" .:—-")
            add_head(i, f"app.{letter}", rest or f"Appendix {letter}")
            continue
        if pg < BODY_START_PAGE:
            continue
        m = HEAD_NUM.match(s)
        if m and _depth(m.group(1)) <= 4:
            nxt = ""
            for j in range(i + 1, min(i + 4, len(records))):
                cand = records[j][1].strip()
                if cand:
                    nxt = cand
                    break
            if _title_ok(nxt):
                add_head(i, m.group(1).rstrip("."), nxt)
                continue
        m2 = HEAD_INLINE.match(s)
        if m2 and _title_ok(m2.group(2)) and _depth(m2.group(1)) <= 4:
            add_head(i, m2.group(1).rstrip("."), m2.group(2))

    # keep first body occurrence of each num (skip TOC duplicates: already pg>=18)
    seen: set[str] = set()
    uniq = []
    for h in heads:
        if h["num"] in seen:
            continue
        seen.add(h["num"])
        uniq.append(h)
    uniq.sort(key=lambda h: h["i"])

    # prepend front matter
    if uniq:
        first_i = uniq[0]["i"]
        front_lines = [records[k][1] for k in range(0, first_i) if records[k][0] < BODY_START_PAGE or k < first_i]
        front_text = "\n".join(front_lines).strip()
        spans = [
            {
                "num": "0",
                "title": "Front matter (disclaimer, revision history, contents)",
                "start_i": 0,
                "end_i": first_i,
                "start_page": 1,
                "end_page": BODY_START_PAGE - 1,
                "text": front_text,
            }
        ]
    else:
        spans = []
        first_i = 0

    for n, h in enumerate(uniq):
        end_i = uniq[n + 1]["i"] if n + 1 < len(uniq) else len(records)
        chunk_lines = [records[k][1] for k in range(h["i"], end_i)]
        pages = [records[k][0] for k in range(h["i"], end_i)]
        spans.append(
            {
                "num": h["num"],
                "title": h["title"],
                "start_i": h["i"],
                "end_i": end_i,
                "start_page": h["page"],
                "end_page": records[end_i - 1][0] if end_i > h["i"] else h["page"],
                "text": "\n".join(chunk_lines).strip(),
            }
        )
    return _merge_small(spans)


def _parent_num(num: str) -> str | None:
    if "." not in str(num):
        return None
    return str(num).rsplit(".", 1)[0]


def _same_merge_family(prev_num: str, num: str) -> bool:
    if str(num).startswith("app") or str(prev_num).startswith("app"):
        return False
    if _depth(num) == 1:
        return False
    if str(num).startswith(str(prev_num) + "."):
        return True
    return _parent_num(num) is not None and _parent_num(num) == _parent_num(prev_num)


def _merge_small(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not spans:
        return spans
    out: list[dict[str, Any]] = []
    for sp in spans:
        num = str(sp["num"])
        tiny = len(sp.get("text") or "") < MIN_CHARS
        if (
            out
            and tiny
            and num not in PROTECTED_SECTIONS
            and _same_merge_family(str(out[-1]["num"]), num)
        ):
            prev = out[-1]
            prev["text"] = (prev["text"] + "\n\n" + sp["text"]).strip()
            prev["end_page"] = sp["end_page"]
            prev["title"] = prev["title"] + " / " + sp["title"]
            continue
        if out and len(out[-1].get("text") or "") > MAX_CHARS:
            out.append(dict(sp))
            continue
        out.append(dict(sp))
    return out


def _prefix_tags(num: str) -> dict[str, list[str]]:
    tags = {k: [] for k in ("gi_phase", "milestone", "actor", "topic", "risk_code", "claim_class")}
    n = num
    if n.startswith("app."):
        tags["claim_class"] = ["study_method"]
        tags["actor"] = ["ic", "miso"]
        return tags
    if n == "0":
        tags["claim_class"] = ["do_not_use_as_legal_opinion"]
        tags["actor"] = ["miso"]
        return tags
    best: dict[str, list[str]] | None = None
    best_len = -1
    for prefix, rule in PREFIX_RULES:
        if n == prefix or n.startswith(prefix + "."):
            if len(prefix) > best_len:
                best = rule
                best_len = len(prefix)
    if best:
        for k, vals in best.items():
            tags[k] = list(vals)
    return tags


def _keyword_fill(tags: dict[str, list[str]], blob: str) -> dict[str, list[str]]:
    for pat, topic in KEYWORD_TOPIC:
        if re.search(pat, blob, re.I):
            if topic not in tags["topic"]:
                tags["topic"].append(topic)
    for pat, ms in KEYWORD_MILESTONE:
        if re.search(pat, blob, re.I) and ms not in tags["milestone"]:
            tags["milestone"].append(ms)
    for pat, actor in KEYWORD_ACTOR:
        if re.search(pat, blob, re.I) and actor not in tags["actor"]:
            tags["actor"].append(actor)
    if not tags["claim_class"]:
        tags["claim_class"] = ["workflow"]
    for k, allowed in (
        ("gi_phase", GI_PHASES),
        ("milestone", MILESTONES),
        ("actor", ACTORS),
        ("topic", TOPICS),
        ("risk_code", tuple(RISK_CODES)),
        ("claim_class", CLAIM_CLASSES),
    ):
        tags[k] = [x for x in dict.fromkeys(tags[k]) if x in allowed]
    return tags


def _stakeholders(actors: list[str]) -> list[dict[str, str]]:
    out = []
    for a in actors:
        out.append({"actor": a, "impact": IMPACT_BY_ACTOR.get(a, a)})
    return out


def span_to_unit(sp: dict[str, Any]) -> dict[str, Any]:
    num = str(sp["num"])
    title = sp["title"]
    tags = _prefix_tags(num)
    tags = _keyword_fill(tags, f"{title}\n{sp['text'][:2500]}")
    if num in TAG_OVERRIDES:
        for k, vals in TAG_OVERRIDES[num].items():
            tags[k] = list(vals)
        for k, allowed in (
            ("gi_phase", GI_PHASES),
            ("milestone", MILESTONES),
            ("actor", ACTORS),
            ("topic", TOPICS),
            ("risk_code", tuple(RISK_CODES)),
            ("claim_class", CLAIM_CLASSES),
        ):
            tags[k] = [x for x in dict.fromkeys(tags[k]) if x in allowed]
    unit_id = f"bpm015-r33::{num}"
    return {
        "unit_id": unit_id,
        "source": {
            "doc_id": DOC_ID,
            "pdf": PDF_NAME,
            "bpm_section": num,
            "title": title,
            "pages": [sp["start_page"], sp["end_page"]],
            "effective_date": EFFECTIVE,
            "status": "current",
        },
        "tags": tags,
        "stakeholders": _stakeholders(tags.get("actor") or ["miso"]),
        "text": sp["text"],
        "cite": f"BPM-015 r33 §{num}" if not num.startswith("app") else f"BPM-015 r33 Appendix {num.split('.')[-1]}",
    }


def build_units() -> list[dict[str, Any]]:
    if not FULL_MD.exists():
        raise FileNotFoundError(f"missing {FULL_MD}; run scripts/harvest_miso_bpm015.py")
    spans = parse_full_md()
    return [span_to_unit(sp) for sp in spans]


def _match_seed(units: list[dict[str, Any]], section: str) -> list[str]:
    exact: list[str] = []
    children: list[str] = []
    parents: list[tuple[int, str]] = []
    for u in units:
        n = str(u["source"]["bpm_section"])
        uid = u["unit_id"]
        if n == section:
            exact.append(uid)
        elif n.startswith(section + "."):
            children.append(uid)
        elif section.startswith(n + "."):
            parents.append((len(n), uid))
    if exact:
        return exact
    if children:
        return children
    if parents:
        parents.sort(reverse=True)
        return [parents[0][1]]
    return []


def build_maps(units: list[dict[str, Any]]) -> dict[str, Any]:
    by_phase: dict[str, list[str]] = {p: [] for p in GI_PHASES}
    by_actor: dict[str, list[str]] = {a: [] for a in ACTORS}
    by_topic: dict[str, list[str]] = {t: [] for t in TOPICS}
    by_milestone: dict[str, list[str]] = {m: [] for m in MILESTONES}
    by_claim: dict[str, list[str]] = {c: [] for c in CLAIM_CLASSES}
    by_risk: dict[str, Any] = {r: {"unit_ids": [], "note": None} for r in RISK_CODES}

    for u in units:
        uid = u["unit_id"]
        tags = u["tags"]
        for p in tags.get("gi_phase") or []:
            by_phase[p].append(uid)
        for a in tags.get("actor") or []:
            by_actor[a].append(uid)
        for t in tags.get("topic") or []:
            if t in by_topic:
                by_topic[t].append(uid)
        for m in tags.get("milestone") or []:
            if m in by_milestone:
                by_milestone[m].append(uid)
        for c in tags.get("claim_class") or []:
            if c in by_claim:
                by_claim[c].append(uid)
        for r in tags.get("risk_code") or []:
            if r in by_risk:
                by_risk[r]["unit_ids"].append(uid)

    for risk, seeds in RISK_SEED_SECTIONS.items():
        if risk in STUB_RISKS:
            by_risk[risk] = {
                "unit_ids": [],
                "note": "No BPM-015 clause. Keep company/stub playbook only. Do not invent a MISO rule.",
            }
            continue
        seeded: list[str] = []
        for sec in seeds:
            seeded.extend(_match_seed(units, sec))
        # Canonical map is the seed clauses, not every descendant tagged by prefix.
        by_risk[risk]["unit_ids"] = list(dict.fromkeys(seeded))
        by_risk[risk]["note"] = None

    return {
        "gi_phase_to_units": {k: list(dict.fromkeys(v)) for k, v in by_phase.items()},
        "actor_to_units": {k: list(dict.fromkeys(v)) for k, v in by_actor.items()},
        "topic_to_units": {k: list(dict.fromkeys(v)) for k, v in by_topic.items()},
        "milestone_to_units": {k: list(dict.fromkeys(v)) for k, v in by_milestone.items()},
        "claim_class_to_units": {k: list(dict.fromkeys(v)) for k, v in by_claim.items()},
        "risk_code_to_units": by_risk,
    }


def write_index(units: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    PROCEDURE_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "packs").mkdir(parents=True, exist_ok=True)
    units = units if units is not None else build_units()
    for old in PROCEDURE_DIR.glob("*.json"):
        old.unlink()
    for u in units:
        safe = u["unit_id"].replace("::", "__").replace(".", "_")
        (PROCEDURE_DIR / f"{safe}.json").write_text(json.dumps(u, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    maps = build_maps(units)
    (INDEX_DIR / "ontology.json").write_text(json.dumps(ontology(), indent=2), encoding="utf-8")
    (MAP_DIR / "gi_phase_to_units.json").write_text(json.dumps(maps["gi_phase_to_units"], indent=2), encoding="utf-8")
    (MAP_DIR / "actor_to_units.json").write_text(json.dumps(maps["actor_to_units"], indent=2), encoding="utf-8")
    (MAP_DIR / "topic_to_units.json").write_text(json.dumps(maps["topic_to_units"], indent=2), encoding="utf-8")
    (MAP_DIR / "milestone_to_units.json").write_text(json.dumps(maps["milestone_to_units"], indent=2), encoding="utf-8")
    (MAP_DIR / "claim_class_to_units.json").write_text(json.dumps(maps["claim_class_to_units"], indent=2), encoding="utf-8")
    (MAP_DIR / "risk_code_to_units.json").write_text(json.dumps(maps["risk_code_to_units"], indent=2), encoding="utf-8")
    (INDEX_DIR / "units.jsonl").write_text(
        "\n".join(json.dumps(u, ensure_ascii=False) for u in units) + "\n", encoding="utf-8"
    )
    from src.modeling.platinum4.catalog import (
        LEXICAL_DIR,
        build_bm25_idf,
        build_ontology_graph,
        build_search_catalog,
    )

    catalog = build_search_catalog(units, maps)
    graph = build_ontology_graph(units, maps)
    (INDEX_DIR / "search_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (INDEX_DIR / "ontology_graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    LEXICAL_DIR.mkdir(parents=True, exist_ok=True)
    (LEXICAL_DIR / "bm25_idf.json").write_text(json.dumps(build_bm25_idf(units)), encoding="utf-8")
    pack_readme = """# Bot packet assembly

`retrieve_for_card(card)` in `src/modeling/platinum4/retrieve.py` is catalog-route only.

`retrieve_for_query(query)` in `src/modeling/platinum4/search.py` unions catalog route, lexicon, seed lookup, inverted maps, phrase match, and BM25, then fuses. `search_trace` logs algorithms and directives.

Composer is gpt-4.1 only (`src/modeling/platinum4/compose.py`). Compliance is `not_determined`.

Index **r33 clean only**. r32/redlines stay under `docs/miso_policy/pdfs/` for humans.
"""
    (INDEX_DIR / "packs" / "README.md").write_text(pack_readme, encoding="utf-8")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "n_units": len(units),
        "n_with_risk": sum(1 for u in units if u["tags"].get("risk_code")),
        "stub_risks": list(STUB_RISKS),
    }
    (INDEX_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
