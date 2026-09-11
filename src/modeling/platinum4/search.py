"""Hybrid retrieval: catalog route, lexicon, seed, inverted maps, phrase, BM25.

GPT does not assign tags. Directives are code. Public API: retrieve_for_query.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from src.modeling.platinum4.catalog import graph_slice, tokenize
from src.modeling.platinum4.errors import (
    EMPTY_QUERY,
    INDEX_MISSING,
    STUB_ONLY,
    TEST_SEALED,
    ZERO_HITS,
    BotError,
)
from src.modeling.platinum4.lexicon import extract_tags, merge_tag_sets
from src.modeling.platinum4.policy_index import (
    DOC_ID,
    INDEX_DIR,
    MAP_DIR,
    RISK_SEED_SECTIONS,
    STUB_RISKS,
    _match_seed,
)
from src.modeling.platinum4.retrieve import (
    MAX_UNITS,
    _flag_topics,
    _score_unit,
    _section_family,
    assemble_bot_packet,
    gi_phases_for_card,
    load_units,
    risk_codes_for_card,
)

QUERY_SCHEMA = "query.v1"
SECTION_RE = re.compile(r"(?:§|section)\s*(\d+(?:\.\d+){0,3})", re.I)
BARE_SECTION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+){0,2})\b")
STUDY_METHOD_RE = re.compile(r"\bstudy method\b|\bmethodology\b|\bpss/?e\b|\bhow does miso study\b", re.I)
GIP_RE = re.compile(r"\bGIP\b|\bAttachment X\b|Section 3\.6 of the GIP", re.I)
DELAY_CLAUSE_RE = re.compile(
    r"\b7\.3\b|\b7\.7\b|cod delay|commercial operation|"
    r"milestone amendment|ic delay|post-?gia delay",
    re.I,
)
CARD_AS_CONTEXT_RE = re.compile(
    r"risk context only|read the card as risk|"
    r"what those flags do and do not|"
    r"do not treat p\(quit\)|do not treat .{0,80} as a BPM duty",
    re.I,
)
SEQUENCE_RE = re.compile(
    r"\b(procedure map|who does what|flowchart|mermaid|sequence of steps)\b",
    re.I,
)

TOPIC_SEEDS: dict[str, list[str]] = {
    "restudy": ["5.4.6"],
    "decision_point": ["5.3.3", "5.2.3"],
    "deposit_refund": ["4.2.4.5", "4.2.4.6", "6.2.11"],
    "commercial_operation": ["7.3", "7.7"],
    "gia_negotiation": ["6.2.7", "6.2.8"],
    "site_control": ["5.1.2"],
    "scoping": ["3.1.1", "4.3"],
    "withdrawal": ["5.2.5", "5.3.5"],
}
MILESTONE_SEEDS: dict[str, list[str]] = {
    "D2": ["4.2.4.5"],
    "M4": ["5.3.3"],
    "M3": ["5.3.3", "6.2.11"],
    "M2": ["5.2.3"],
}


def _now_ms() -> float:
    return time.perf_counter()


def _alg_row(name: str, hits: list[dict[str, Any]], t0: float, error: str | None = None) -> dict[str, Any]:
    elapsed = int((time.perf_counter() - t0) * 1000)
    return {
        "name": name,
        "n_candidates": len(hits),
        "top_ids": [h["unit_id"] for h in hits[:5]],
        "elapsed_ms": elapsed,
        "error": error,
    }


def _directive(name: str, ok: bool, reason: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "reason": reason}


def normalize_query(query: dict[str, Any] | None) -> dict[str, Any]:
    q = dict(query or {})
    req = dict(q.get("requirements") or {})
    req.setdefault("audience", "analyst")
    req.setdefault("dialect", "bpm_register")
    req.setdefault("need", ["workflow", "stakeholders", "citations", "do_not_claim"])
    req.setdefault("max_units", MAX_UNITS)
    q["requirements"] = req
    q["schema_version"] = QUERY_SCHEMA
    q["question"] = str(q.get("question") or "").strip()
    return q


def wants_diagram(query: dict[str, Any]) -> bool:
    need = (query.get("requirements") or {}).get("need") or []
    if "diagram" in need:
        return True
    return bool(SEQUENCE_RE.search(query.get("question") or ""))


def load_maps() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in (
        "gi_phase_to_units",
        "actor_to_units",
        "topic_to_units",
        "milestone_to_units",
        "claim_class_to_units",
        "risk_code_to_units",
    ):
        path = MAP_DIR / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def load_graph() -> dict[str, Any]:
    path = INDEX_DIR / "ontology_graph.json"
    if not path.exists():
        return {"nodes": [], "edges": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_bm25() -> dict[str, Any]:
    path = INDEX_DIR / "lexical" / "bm25_idf.json"
    if not path.exists():
        return {"idf": {}, "avgdl": 1.0, "k1": 1.5, "b": 0.75}
    return json.loads(path.read_text(encoding="utf-8"))


def _unit_blob(unit: dict[str, Any]) -> str:
    src = unit.get("source") or {}
    return " ".join(
        [
            str(src.get("title") or ""),
            str(unit.get("cite") or ""),
            str(unit.get("text") or "")[:2000],
        ]
    )


def _is_r32(unit: dict[str, Any]) -> bool:
    uid = str(unit.get("unit_id") or "")
    doc = str((unit.get("source") or {}).get("doc_id") or "")
    blob = f"{uid} {doc}".lower()
    return "r32" in blob or "redline" in blob


def _is_current(unit: dict[str, Any]) -> bool:
    doc = str((unit.get("source") or {}).get("doc_id") or DOC_ID)
    return doc == DOC_ID and not _is_r32(unit)


def _ids_from_map(lookup: dict[str, Any], keys: list[str]) -> list[str]:
    ids: list[str] = []
    for k in keys:
        val = lookup.get(k)
        if isinstance(val, dict):
            ids.extend(val.get("unit_ids") or [])
        elif isinstance(val, list):
            ids.extend(val)
    return list(dict.fromkeys(ids))


def alg_catalog_route(
    units: list[dict[str, Any]],
    card: dict[str, Any] | None,
    maps: dict[str, Any],
) -> list[dict[str, Any]]:
    if not card:
        return []
    by_id = {u["unit_id"]: u for u in units}
    phases = gi_phases_for_card(card)
    risks = risk_codes_for_card(card)
    topics = _flag_topics(card)
    ids: list[str] = []
    ids.extend(_ids_from_map(maps.get("gi_phase_to_units") or {}, phases))
    live_risks = [r for r in risks if r not in STUB_RISKS]
    ids.extend(_ids_from_map(maps.get("risk_code_to_units") or {}, live_risks))
    ids.extend(_ids_from_map(maps.get("topic_to_units") or {}, topics))
    hits = []
    for uid in ids:
        u = by_id.get(uid)
        if not u:
            continue
        s = _score_unit(u, phases, live_risks, topics)
        hits.append({"unit_id": uid, "score": max(s, 0.1), "reason": "catalog_route"})
    hits.sort(key=lambda h: -h["score"])
    return hits


def alg_lexicon(question: str) -> dict[str, list[str]]:
    return extract_tags(question)


def alg_seed_lookup(units: list[dict[str, Any]], risks: list[str]) -> list[dict[str, Any]]:
    hits = []
    seen: set[str] = set()
    for r in risks:
        if r in STUB_RISKS:
            continue
        for sec in RISK_SEED_SECTIONS.get(r) or []:
            for uid in _match_seed(units, sec):
                if uid in seen:
                    continue
                seen.add(uid)
                hits.append({"unit_id": uid, "score": 5.0, "reason": f"seed:{r}:{sec}"})
    return hits


def alg_inverted_filter(
    units: list[dict[str, Any]],
    maps: dict[str, Any],
    tags: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], str]:
    by_id = {u["unit_id"]: u for u in units}
    ids: list[str] = []
    ids.extend(_ids_from_map(maps.get("gi_phase_to_units") or {}, tags.get("gi_phase") or []))
    ids.extend(_ids_from_map(maps.get("topic_to_units") or {}, tags.get("topic") or []))
    ids.extend(_ids_from_map(maps.get("milestone_to_units") or {}, tags.get("milestone") or []))
    ids.extend(_ids_from_map(maps.get("claim_class_to_units") or {}, tags.get("claim_class") or []))
    live_risks = [r for r in (tags.get("risk_code") or []) if r not in STUB_RISKS]
    ids.extend(_ids_from_map(maps.get("risk_code_to_units") or {}, live_risks))
    ids.extend(_ids_from_map(maps.get("actor_to_units") or {}, tags.get("actor") or []))
    ids = list(dict.fromkeys(ids))
    mode = "inverted_or"
    if not ids:
        mode = "fallback_broad"
        for u in units:
            claim = (u.get("tags") or {}).get("claim_class") or []
            if "study_method" in claim and "workflow" not in claim:
                continue
            ids.append(u["unit_id"])
    hits = []
    for uid in ids:
        if uid in by_id:
            hits.append({"unit_id": uid, "score": 1.0, "reason": mode})
    return hits, mode


def alg_phrase_match(units: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    if not question:
        return []
    q = question.lower()
    wanted_sections: list[str] = []
    for m in SECTION_RE.findall(question):
        wanted_sections.append(m)
    for m in BARE_SECTION_RE.findall(question):
        if m.count(".") >= 1:
            wanted_sections.append(m)
    hits: list[dict[str, Any]] = []
    for u in units:
        src = u.get("source") or {}
        num = str(src.get("bpm_section") or "")
        title = str(src.get("title") or "")
        title_l = title.lower()
        score = 0.0
        reason = "phrase"
        if num and num in wanted_sections:
            score = 1.0
            reason = f"section:{num}"
        elif title_l and len(title_l) >= 12 and title_l in q:
            score = 0.85
            reason = "title_in_question"
        else:
            words = [w for w in tokenize(title) if len(w) >= 4]
            overlap = [w for w in words if w in q.split() or w in tokenize(q)]
            if len(overlap) >= 2:
                score = 0.4 + 0.1 * min(len(overlap), 4)
                reason = "title_overlap"
        if score > 0:
            hits.append({"unit_id": u["unit_id"], "score": score, "reason": reason})
    hits.sort(key=lambda h: -h["score"])
    return hits


def alg_bm25(
    units: list[dict[str, Any]],
    question: str,
    sidecar: dict[str, Any],
    *,
    query_override: str | None = None,
) -> list[dict[str, Any]]:
    qtext = query_override if query_override is not None else question
    if not qtext:
        return []
    qtoks = tokenize(qtext)
    if not qtoks:
        return []
    idf = sidecar.get("idf") or {}
    avgdl = float(sidecar.get("avgdl") or 1.0) or 1.0
    k1 = float(sidecar.get("k1") or 1.5)
    b = float(sidecar.get("b") or 0.75)
    hits = []
    for u in units:
        toks = tokenize(_unit_blob(u))
        if not toks:
            continue
        dl = len(toks)
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t in qtoks:
            if t not in tf or t not in idf:
                continue
            freq = tf[t]
            score += float(idf[t]) * (freq * (k1 + 1.0)) / (freq + k1 * (1.0 - b + b * dl / avgdl))
        if score > 0:
            hits.append({"unit_id": u["unit_id"], "score": score, "reason": "bm25"})
    hits.sort(key=lambda h: -h["score"])
    return hits


def _minmax(vals: dict[str, float]) -> dict[str, float]:
    if not vals:
        return {}
    lo = min(vals.values())
    hi = max(vals.values())
    if hi <= lo:
        return {k: 1.0 for k in vals}
    return {k: (v - lo) / (hi - lo) for k, v in vals.items()}


def alg_fusion(
    units: list[dict[str, Any]],
    tag_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
    phrase_hits: list[dict[str, Any]],
    seed_ids: set[str],
    *,
    prefer_workflow: bool,
    restudy: bool,
    cod: bool,
) -> list[dict[str, Any]]:
    by_id = {u["unit_id"]: u for u in units}
    tag_raw = {h["unit_id"]: h["score"] for h in tag_hits}
    bm_raw = {h["unit_id"]: h["score"] for h in bm25_hits}
    ph_raw = {h["unit_id"]: h["score"] for h in phrase_hits}
    pool = set(tag_raw) | set(bm_raw) | set(ph_raw)
    tag_n = _minmax(tag_raw)
    bm_n = _minmax(bm_raw)
    ph_n = _minmax(ph_raw)
    fused = []
    for uid in pool:
        u = by_id.get(uid)
        if not u:
            continue
        score = 0.55 * tag_n.get(uid, 0.0) + 0.30 * bm_n.get(uid, 0.0) + 0.15 * ph_n.get(uid, 0.0)
        if uid in seed_ids:
            score += 0.20
        tags = u.get("tags") or {}
        claim = tags.get("claim_class") or []
        if restudy and "restudy" in (tags.get("topic") or []):
            score += 0.12
        if cod and "cod_already_slipped" in (tags.get("risk_code") or []):
            score += 0.12
        if "workflow" in claim:
            score += 0.08
        if prefer_workflow and "study_method" in claim and "workflow" not in claim:
            score -= 0.25
        fused.append({"unit_id": uid, "score": score, "reason": "fusion"})
    fused.sort(key=lambda h: -h["score"])
    return fused


def _apply_family_cap(
    ranked: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    seed_ids: set[str],
    max_units: int,
    locked: set[str] | None = None,
) -> list[dict[str, Any]]:
    locked = locked or set()
    picked: list[dict[str, Any]] = []
    family_n: dict[str, int] = {}
    seen: set[str] = set()

    def _add(h: dict[str, Any], *, ignore_cap: bool) -> bool:
        uid = h["unit_id"]
        if uid in seen:
            return False
        u = by_id.get(uid)
        if not u:
            return False
        num = str((u.get("source") or {}).get("bpm_section") or "")
        fam = _section_family(num)
        cap = 4 if uid in locked else (3 if uid in seed_ids else 2)
        if not ignore_cap and family_n.get(fam, 0) >= cap:
            return False
        seen.add(uid)
        family_n[fam] = family_n.get(fam, 0) + 1
        picked.append(h)
        return True

    by_rank = {h["unit_id"]: h for h in ranked}
    for uid in locked:
        h = by_rank.get(uid) or {"unit_id": uid, "score": 9.0, "reason": "required_seed"}
        _add(h, ignore_cap=True)
        if len(picked) >= max_units:
            return picked
    for h in ranked:
        if len(picked) >= max_units:
            break
        _add(h, ignore_cap=False)
    return picked


def required_unit_ids(question: str, lex: dict[str, list[str]], units: list[dict[str, Any]]) -> list[str]:
    """Exact seed clauses the question named. Locked through family cap."""
    q = (question or "").lower()
    secs: list[str] = []
    if re.search(r"decision point ii|\bdp[\s-]?ii\b|\bdecision point 2\b", question or "", re.I):
        secs.extend(["5.3.3"])
    elif "decision_point" in (lex.get("topic") or []):
        secs.extend(["5.2.3", "5.3.3"])
    for topic in lex.get("topic") or []:
        if topic == "decision_point":
            continue
        if topic == "gia_negotiation" and not re.search(
            r"gia execution|filed unexecuted|appendix review|negotiate the gia",
            question or "",
            re.I,
        ):
            continue
        if topic == "commercial_operation" and not DELAY_CLAUSE_RE.search(question or ""):
            continue
        if topic == "deposit_refund" and not re.search(
            r"\bD2\b|study funding|refund", question or "", re.I
        ):
            continue
        if topic == "withdrawal" and "restud" in q:
            continue
        secs.extend(TOPIC_SEEDS.get(topic) or [])
    for m in lex.get("milestone") or []:
        secs.extend(MILESTONE_SEEDS.get(m) or [])
    if DELAY_CLAUSE_RE.search(question or ""):
        secs.extend(["7.3", "7.7"])
    if "restud" in q:
        secs.extend(["5.4.6"])
    if re.search(r"\bD2\b|study funding", question or "", re.I):
        secs.extend(["4.2.4.5"])
    if re.search(r"\bM3\b|\bM4\b|milestone deposit", question or "", re.I):
        secs.extend(["6.2.11"])
    if re.search(r"\bsuspension\b", question or "", re.I):
        secs.extend(["7.1"])
    if re.search(r"\bsite control\b", question or "", re.I):
        secs.extend(["5.1.2"])
    ids: list[str] = []
    for sec in list(dict.fromkeys(secs)):
        ids.extend(_match_seed(units, sec))
    return list(dict.fromkeys(ids))


def retrieve_for_query(query: dict[str, Any] | None, *, units: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Card and/or question -> bot packet with search_trace and graph_slice."""
    q = normalize_query(query)
    question = q.get("question") or ""
    card = q.get("card")
    if isinstance(card, dict) and not card:
        card = None
    req = q["requirements"]
    if q.get("split") == "test":
        raise BotError(TEST_SEALED, "2024 test is sealed. Do not retrieve for split=test.")
    if not question and not card:
        raise BotError(EMPTY_QUERY, "No question and no card. Abort.")
    try:
        units = units if units is not None else load_units()
    except FileNotFoundError as exc:
        raise BotError(INDEX_MISSING, str(exc)) from exc

    maps = load_maps()
    graph = load_graph()
    sidecar = load_bm25()
    by_id = {u["unit_id"]: u for u in units}
    directives: list[dict[str, Any]] = []
    algorithms: list[dict[str, Any]] = []
    gaps: list[str] = []

    lex_tags = alg_lexicon(question) if question else {}
    if GIP_RE.search(question or ""):
        gaps.append("The GIP (Attachment X) is the tariff and is not in this packet.")

    card_as_context = bool(CARD_AS_CONTEXT_RE.search(question or ""))
    card_phases = gi_phases_for_card(card) if card and not card_as_context else []
    card_risks = risk_codes_for_card(card) if card else []
    card_topics = _flag_topics(card) if card and not card_as_context else []
    live_card_risks = [r for r in card_risks if r not in STUB_RISKS]
    if card_as_context:
        live_card_risks = []
    stub_asked = [r for r in (card_risks + (lex_tags.get("risk_code") or [])) if r in STUB_RISKS]
    merged_tags = merge_tag_sets(
        lex_tags,
        {
            "gi_phase": card_phases,
            "risk_code": live_card_risks,
            "topic": card_topics,
        },
    )
    seed_risks = list(dict.fromkeys(live_card_risks + (lex_tags.get("risk_code") or [])))
    seed_risks = [r for r in seed_risks if r not in STUB_RISKS]
    study_q = bool(STUDY_METHOD_RE.search(question))
    prefer_workflow = not study_q
    required_ids = required_unit_ids(question, lex_tags, units)
    max_units = int(req.get("max_units") or MAX_UNITS)
    max_units = max(max_units, min(16, len(required_ids) + 2))

    t0 = _now_ms()
    catalog_hits = [] if card_as_context else alg_catalog_route(units, card, maps)
    algorithms.append(_alg_row("alg_catalog_route", catalog_hits, t0))

    t0 = _now_ms()
    algorithms.append(
        {
            "name": "alg_lexicon",
            "n_candidates": sum(len(v) for v in lex_tags.values()),
            "top_ids": [],
            "tags": lex_tags,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "error": None,
        }
    )

    t0 = _now_ms()
    seed_hits = alg_seed_lookup(units, seed_risks)
    algorithms.append(_alg_row("alg_seed_lookup", seed_hits, t0))
    seed_ids = {h["unit_id"] for h in seed_hits} | set(required_ids)

    t0 = _now_ms()
    inv_hits, inv_mode = alg_inverted_filter(units, maps, merged_tags)
    algorithms.append(_alg_row("alg_inverted_filter", inv_hits, t0))
    algorithms[-1]["mode"] = inv_mode

    t0 = _now_ms()
    phrase_hits = alg_phrase_match(units, question)
    algorithms.append(_alg_row("alg_phrase_match", phrase_hits, t0))

    t0 = _now_ms()
    bm25_hits = alg_bm25(units, question, sidecar)
    algorithms.append(_alg_row("alg_bm25", bm25_hits, t0))

    tag_hits: list[dict[str, Any]] = []
    tag_best: dict[str, float] = {}
    for bucket in (catalog_hits, seed_hits, inv_hits):
        for h in bucket:
            tag_best[h["unit_id"]] = max(tag_best.get(h["unit_id"], 0.0), float(h["score"]))
    tag_hits = [{"unit_id": uid, "score": s, "reason": "tag"} for uid, s in tag_best.items()]

    t0 = _now_ms()
    fused = alg_fusion(
        units,
        tag_hits,
        bm25_hits,
        phrase_hits,
        seed_ids,
        prefer_workflow=prefer_workflow,
        restudy="restudy" in (merged_tags.get("topic") or []),
        cod=(not card_as_context)
        and (
            "cod_already_slipped" in (merged_tags.get("risk_code") or [])
            or "commercial_operation" in (merged_tags.get("topic") or [])
        ),
    )
    algorithms.append(_alg_row("alg_fusion", fused, t0))

    # Directives on the ranked pool.
    directives.append(_directive("DIR_EMPTY_INPUT", True, "question and/or card present"))
    current_ok = True
    filtered: list[dict[str, Any]] = []
    for h in fused:
        u = by_id.get(h["unit_id"])
        if not u:
            continue
        if _is_r32(u):
            current_ok = False
            continue
        if not _is_current(u):
            current_ok = False
            continue
        filtered.append(h)
    directives.append(
        _directive("DIR_REQUIRE_CURRENT_DOC", current_ok, "kept status:current r33 units only")
    )
    directives.append(_directive("DIR_NO_R32", True, "r32/redline unit ids never added"))

    if stub_asked:
        gaps.extend(
            f"{code} has no BPM-015 clause" for code in dict.fromkeys(stub_asked)
        )
        directives.append(
            _directive(
                "DIR_STUB_HONESTY",
                True,
                "stub risks retrieved nothing; gaps recorded",
            )
        )
    else:
        directives.append(_directive("DIR_STUB_HONESTY", True, "no stub risk in this query"))

    legal_drop = []
    kept_no_legal = []
    for h in filtered:
        u = by_id[h["unit_id"]]
        claim = (u.get("tags") or {}).get("claim_class") or []
        if "do_not_use_as_legal_opinion" in claim:
            legal_drop.append(h)
        else:
            kept_no_legal.append(h)
    if kept_no_legal:
        filtered = kept_no_legal
        directives.append(
            _directive("DIR_DROP_LEGAL_OPINION", True, "dropped do_not_use_as_legal_opinion")
        )
    else:
        directives.append(
            _directive("DIR_DROP_LEGAL_OPINION", True, "pool empty without legal-opinion units; kept them")
        )

    if prefer_workflow:
        directives.append(
            _directive("DIR_PREFER_WORKFLOW", True, "study_method downranked unless the question is about study method")
        )
    else:
        directives.append(_directive("DIR_PREFER_WORKFLOW", True, "study method question; no downrank"))

    audience = str(req.get("audience") or "analyst")
    if audience == "ic":
        ic_hits = [
            h
            for h in filtered
            if "ic"
            in (((by_id.get(h["unit_id"]) or {}).get("tags") or {}).get("actor") or [])
        ]
        if ic_hits:
            filtered = ic_hits
            directives.append(_directive("DIR_AUDIENCE_ACTOR", True, "kept units whose actor includes ic"))
        else:
            directives.append(_directive("DIR_AUDIENCE_ACTOR", True, "no ic-tagged unit in pool; kept pool"))
    else:
        directives.append(_directive("DIR_AUDIENCE_ACTOR", True, f"audience={audience}; no ic filter"))

    picked_hits = _apply_family_cap(filtered, by_id, seed_ids, max_units, locked=set(required_ids))
    directives.append(_directive("DIR_FAMILY_CAP", True, "max 2 units per section family, 3 if seed; required seeds locked"))

    # Coverage pass: fill missing lexicon facets; do not evict required seeds.
    t0 = _now_ms()
    coverage_added: list[str] = []
    kept_ids = {h["unit_id"] for h in picked_hits}
    needed_topics = list(lex_tags.get("topic") or [])
    needed_risks = [r for r in (lex_tags.get("risk_code") or []) if r not in STUB_RISKS]
    if not re.search(r"\bcontour\b|\bgrouping\b|\bnetwork congestion\b", question or "", re.I):
        needed_risks = [r for r in needed_risks if r != "system_congestion"]
    miss_topics = []
    for topic in needed_topics:
        if not any(topic in ((by_id.get(h["unit_id"]) or {}).get("tags") or {}).get("topic") or [] for h in picked_hits):
            miss_topics.append(topic)
    miss_risks = []
    for risk in needed_risks:
        if not any(risk in ((by_id.get(h["unit_id"]) or {}).get("tags") or {}).get("risk_code") or [] for h in picked_hits):
            miss_risks.append(risk)
    extra_bm: list[dict[str, Any]] = []
    for term in miss_topics + miss_risks:
        extra = alg_bm25(units, question, sidecar, query_override=term.replace("_", " "))
        extra_bm.extend(extra[:3])
        for h in extra:
            if h["unit_id"] in kept_ids:
                continue
            u = by_id.get(h["unit_id"])
            if not u or _is_r32(u):
                continue
            picked_hits.append({"unit_id": h["unit_id"], "score": h["score"], "reason": "coverage_repair"})
            kept_ids.add(h["unit_id"])
            coverage_added.append(h["unit_id"])
            break
        if len(picked_hits) >= max_units + 4:
            break
    picked_hits = _apply_family_cap(
        picked_hits, by_id, seed_ids, max_units, locked=set(required_ids) | set(coverage_added)
    )
    algorithms.append(_alg_row("alg_coverage_pass", extra_bm, t0))
    algorithms[-1]["coverage_repair"] = coverage_added

    still_miss = []
    for topic in needed_topics:
        if not any(topic in ((by_id.get(h["unit_id"]) or {}).get("tags") or {}).get("topic") or [] for h in picked_hits):
            still_miss.append(topic)
            gaps.append(f"no unit kept for lexicon topic {topic}")
    for risk in needed_risks:
        if not any(risk in ((by_id.get(h["unit_id"]) or {}).get("tags") or {}).get("risk_code") or [] for h in picked_hits):
            still_miss.append(risk)
            gaps.append(f"no unit kept for lexicon risk {risk}")
    directives.append(
        _directive(
            "DIR_COVERAGE",
            not still_miss,
            "all lexicon topics/risks have a kept unit" if not still_miss else f"miss: {still_miss}",
        )
    )

    picked_units = [by_id[h["unit_id"]] for h in picked_hits if h["unit_id"] in by_id]
    error_code = None
    if not picked_units:
        if stub_asked and not live_card_risks and not needed_topics:
            error_code = STUB_ONLY
            gaps.append("No BPM-015 clause was retrieved for the stub risk(s).")
        else:
            error_code = ZERO_HITS
            gaps.append("No procedure unit matched the question and card tags.")

    extra = {
        "query": {
            "schema_version": QUERY_SCHEMA,
            "question": question or None,
            "requirements": req,
            "has_card": bool(card),
        },
        "gaps": list(dict.fromkeys(gaps)),
        "search_trace": {
            "algorithms": algorithms,
            "directives": directives,
            "lexicon_tags": lex_tags,
            "seed_ids": sorted(seed_ids),
            "kept_unit_ids": [u["unit_id"] for u in picked_units],
        },
        "error_code": error_code,
    }
    extra["graph_slice"] = graph_slice(
        [u["unit_id"] for u in picked_units],
        graph,
        algorithms,
    )
    extra["wants_diagram"] = wants_diagram(q)

    phases = card_phases or list(merged_tags.get("gi_phase") or [])
    risks = list(dict.fromkeys(card_risks + (lex_tags.get("risk_code") or [])))
    packet = assemble_bot_packet(card, picked_units, units, phases, risks, extra=extra)
    return packet


def packet_from_unit_ids(
    unit_ids: list[str],
    query: dict[str, Any] | None = None,
    *,
    units: list[dict[str, Any]] | None = None,
    reason: str = "history_reuse",
) -> dict[str, Any]:
    """Build a bot packet from units already in the thread. No new search."""
    q = normalize_query(query)
    card = q.get("card")
    if isinstance(card, dict) and not card:
        card = None
    try:
        units = units if units is not None else load_units()
    except FileNotFoundError as exc:
        raise BotError(INDEX_MISSING, str(exc)) from exc
    by_id = {u["unit_id"]: u for u in units}
    picked = [by_id[uid] for uid in unit_ids if uid in by_id]
    phases = gi_phases_for_card(card) if card else []
    risks = risk_codes_for_card(card) if card else []
    gaps: list[str] = []
    if GIP_RE.search(str(q.get("question") or "")):
        gaps.append("The GIP (Attachment X) is the tariff and is not in this packet.")
    if not picked:
        gaps.append("No held procedure unit matched this follow-up.")
    extra = {
        "query": {
            "schema_version": QUERY_SCHEMA,
            "question": q.get("question") or None,
            "requirements": q.get("requirements"),
            "has_card": bool(card),
        },
        "gaps": gaps,
        "search_trace": {
            "algorithms": [
                {
                    "name": "alg_history_reuse",
                    "n_candidates": len(picked),
                    "top_ids": [u["unit_id"] for u in picked[:5]],
                    "elapsed_ms": 0,
                    "error": None,
                    "reason": reason,
                }
            ],
            "directives": [_directive("DIR_HISTORY_REUSE", True, reason)],
            "lexicon_tags": extract_tags(q.get("question") or "") if q.get("question") else {},
            "seed_ids": [],
            "kept_unit_ids": [u["unit_id"] for u in picked],
        },
        "error_code": None if picked else ZERO_HITS,
        "wants_diagram": wants_diagram(q),
        "reused_from_history": True,
    }
    extra["graph_slice"] = graph_slice(
        [u["unit_id"] for u in picked],
        load_graph(),
        extra["search_trace"]["algorithms"],
    )
    return assemble_bot_packet(card, picked, units, phases, risks, extra=extra)

