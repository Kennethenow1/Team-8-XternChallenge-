"""Search catalog, ontology graph, and BM25 IDF sidecar for Platinum 4."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from src.modeling.platinum3.schema import RISK_CODES
from src.modeling.platinum4.policy_index import (
    ACTORS,
    CLAIM_CLASSES,
    DOC_ID,
    EFFECTIVE,
    GI_PHASES,
    INDEX_DIR,
    MILESTONES,
    SCHEMA_VERSION,
    STUB_RISKS,
    TOPICS,
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
LEXICAL_DIR = INDEX_DIR / "lexical"


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall((text or "").lower()) if len(t) >= 2]


def _shelf(facet: str, tag: str, ids: list[str], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cites = []
    for uid in ids[:4]:
        u = by_id.get(uid)
        if u:
            cites.append(u.get("cite"))
    return {"facet": facet, "tag": tag, "n": len(ids), "unit_ids": ids, "example_cites": cites}


def build_search_catalog(units: list[dict[str, Any]], maps: dict[str, Any]) -> dict[str, Any]:
    by_id = {u["unit_id"]: u for u in units}
    shelves: list[dict[str, Any]] = []
    for facet, lookup in (
        ("gi_phase", maps.get("gi_phase_to_units") or {}),
        ("actor", maps.get("actor_to_units") or {}),
        ("topic", maps.get("topic_to_units") or {}),
        ("milestone", maps.get("milestone_to_units") or {}),
        ("claim_class", maps.get("claim_class_to_units") or {}),
    ):
        for tag, ids in lookup.items():
            shelves.append(_shelf(facet, tag, list(ids), by_id))
    risk_map = maps.get("risk_code_to_units") or {}
    for code, entry in risk_map.items():
        ids = list(entry.get("unit_ids") or [])
        row = _shelf("risk_code", code, ids, by_id)
        row["note"] = entry.get("note")
        row["stub"] = code in STUB_RISKS
        shelves.append(row)

    section_tree = []
    for u in units:
        src = u.get("source") or {}
        tags = u.get("tags") or {}
        section_tree.append(
            {
                "unit_id": u["unit_id"],
                "bpm_section": src.get("bpm_section"),
                "title": src.get("title"),
                "pages": src.get("pages"),
                "gi_phase": tags.get("gi_phase") or [],
                "topic": tags.get("topic") or [],
                "claim_class": tags.get("claim_class") or [],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": DOC_ID,
        "effective_date": EFFECTIVE,
        "status": "current",
        "n_units": len(units),
        "shelves": shelves,
        "section_tree": section_tree,
        "routes": {
            "card_only": ["alg_catalog_route", "alg_seed_lookup", "alg_inverted_filter", "alg_fusion"],
            "question": [
                "alg_lexicon",
                "alg_phrase_match",
                "alg_bm25",
                "alg_seed_lookup",
                "alg_inverted_filter",
                "alg_fusion",
                "alg_coverage_pass",
            ],
            "card_and_question": [
                "alg_catalog_route",
                "alg_lexicon",
                "alg_phrase_match",
                "alg_bm25",
                "alg_seed_lookup",
                "alg_inverted_filter",
                "alg_fusion",
                "alg_coverage_pass",
            ],
        },
        "holes": {
            "stub_risks": list(STUB_RISKS),
            "not_retrieved": ["bpm-015-r32-clean", "bpm-015-r33-redlines"],
            "giq_coarser_than_dpp": True,
        },
        "query_examples": [
            {
                "question": "Who funds a restudy if a peer withdraws?",
                "expected_unit_ids": ["bpm015-r33::5.4.6"],
            },
            {
                "question": "What happens at Decision Point II?",
                "expected_unit_ids": ["bpm015-r33::5.3.3"],
            },
            {
                "question": "What delay clauses apply after GIA when COD has already passed?",
                "expected_unit_ids": ["bpm015-r33::7.3", "bpm015-r33::7.7"],
            },
            {
                "question": "What is the DPP Study Funding Deposit D2?",
                "expected_unit_ids": ["bpm015-r33::4.2.4.5"],
            },
        ],
    }


def build_ontology_graph(units: list[dict[str, Any]], maps: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(nid: str, kind: str, **extra: Any) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, **extra}

    add_node(f"doc:{DOC_ID}", "doc", title="BPM-015 r33 clean", status="current")
    for code in RISK_CODES:
        add_node(f"risk:{code}", "risk", stub=code in STUB_RISKS)
    for facet, values in (
        ("gi_phase", GI_PHASES),
        ("topic", TOPICS),
        ("milestone", MILESTONES),
        ("actor", ACTORS),
        ("claim_class", CLAIM_CLASSES),
    ):
        for v in values:
            add_node(f"tag:{facet}:{v}", "tag", facet=facet, value=v)

    section_ids = {str((u.get("source") or {}).get("bpm_section")): u["unit_id"] for u in units}
    for u in units:
        uid = u["unit_id"]
        src = u.get("source") or {}
        add_node(
            f"unit:{uid}",
            "unit",
            title=src.get("title"),
            cite=u.get("cite"),
            pages=src.get("pages"),
            bpm_section=src.get("bpm_section"),
        )
        edges.append({"from": f"doc:{DOC_ID}", "to": f"unit:{uid}", "rel": "contains"})
        tags = u.get("tags") or {}
        for facet in ("gi_phase", "topic", "milestone", "actor", "claim_class"):
            for v in tags.get(facet) or []:
                edges.append({"from": f"unit:{uid}", "to": f"tag:{facet}:{v}", "rel": "tagged_with"})
        num = str(src.get("bpm_section") or "")
        if "." in num:
            parent = num.rsplit(".", 1)[0]
            pid = section_ids.get(parent)
            if pid:
                edges.append({"from": f"unit:{pid}", "to": f"unit:{uid}", "rel": "parent_of"})

    risk_map = maps.get("risk_code_to_units") or {}
    for code, entry in risk_map.items():
        for uid in entry.get("unit_ids") or []:
            edges.append({"from": f"unit:{uid}", "to": f"risk:{code}", "rel": "seed_for"})

    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": list(nodes.values()),
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }


def build_bm25_idf(units: list[dict[str, Any]]) -> dict[str, Any]:
    docs: list[list[str]] = []
    df: Counter[str] = Counter()
    for u in units:
        src = u.get("source") or {}
        blob = " ".join(
            [
                str(src.get("title") or ""),
                str(u.get("cite") or ""),
                str(u.get("text") or "")[:2000],
            ]
        )
        toks = tokenize(blob)
        docs.append(toks)
        df.update(set(toks))
    n = max(len(docs), 1)
    idf = {t: math.log((n - c + 0.5) / (c + 0.5) + 1.0) for t, c in df.items()}
    avgdl = sum(len(d) for d in docs) / n
    return {
        "schema_version": SCHEMA_VERSION,
        "n_docs": n,
        "avgdl": avgdl,
        "k1": 1.5,
        "b": 0.75,
        "idf": idf,
    }


def graph_slice(unit_ids: list[str], graph: dict[str, Any], algorithms: list[dict[str, Any]]) -> dict[str, Any]:
    keep_units = {f"unit:{uid}" for uid in unit_ids}
    extra: set[str] = set()
    edges = []
    for e in graph.get("edges") or []:
        if e.get("from") in keep_units or e.get("to") in keep_units:
            edges.append(e)
            extra.add(str(e.get("from")))
            extra.add(str(e.get("to")))
    keep = keep_units | extra | {f"doc:{DOC_ID}"}
    nodes = [n for n in graph.get("nodes") or [] if n["id"] in keep]
    return {
        "unit_ids": unit_ids,
        "nodes": nodes,
        "edges": edges,
        "algorithms": [a.get("name") for a in algorithms],
    }
