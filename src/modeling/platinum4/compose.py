"""gpt-4.1 composition: plan, then write. Code post-check is not an LLM call.

Pinned model is gpt-4.1. No silent fallback to another chat model.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv

from src.common.paths import REPO_ROOT
from src.modeling.platinum3.schema import DO_NOT_CLAIM
from src.modeling.platinum4.dialect import (
    BANNED_PHRASES,
    OPENER_BANS,
    normalize_shape,
    sample_zero_hits,
    writer_pack,
)
from src.modeling.platinum4.lexicon import extract_tags
from src.modeling.platinum4.session import held_catalog, held_unit_ids, history_for_model
from src.modeling.platinum4.gold_stack import gold_stack_for_model
from src.modeling.platinum4.errors import (
    INVENTED_CITE,
    MERMAID_INVALID,
    OPENAI_AUTH,
    OPENAI_BAD_MODEL,
    OPENAI_MISSING_KEY,
    OPENAI_RATE_LIMIT,
    OPENAI_TIMEOUT,
    PACKET_TOO_LARGE,
    STUB_ONLY,
    ZERO_HITS,
    BotError,
)

PINNED_MODEL = "gpt-4.1"
API_URL = "https://api.openai.com/v1/chat/completions"
MODEL_TEXT_CAP = 1500
COMPOSE_TIMEOUT = 90

CITE_RE = re.compile(r"BPM-015 r33 §(\d+(?:\.\d+)*)")
APP_CITE_RE = re.compile(r"BPM-015 r33 Appendix ([A-Z])")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
MERMAID_FENCE = re.compile(r"```mermaid\s*\n(.*?)```", re.S)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.M)
NODE_ID_RE = re.compile(r"(?:^|\n)\s*([A-Za-z][A-Za-z0-9]*)\s*(?:\[|-->|---)")
DASH_RE = re.compile("[\u2013\u2014]")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF]")
URL_RE = re.compile(r"https?://")
GIP_NOTE = "The GIP (Attachment X) is the tariff and is not in this packet."
GIA_VOID_RE = re.compile(
    r"GIA would no longer be in effect|"
    r"GIA (is|would be) no longer in effect|"
    r"GIA (is|was) (void|terminated)|"
    r"voids the (executed )?GIA|"
    r"automatically voids the GIA|"
    r"would no longer be in effect for that project|"
    r"delay (clause|provisions) would not apply|"
    r"(section|§)\s*7\.3 would not apply",
    re.I,
)
HONEST_GIA = (
    "BPM-015 r33 §5.4.6 treats a missed restudy-notice window as deemed withdrawal of the IR. "
    "This packet does not say that an already-executed GIA is terminated, or that BPM-015 r33 §7.3 "
    "stops applying. Whether the tariff (GIP / Attachment X) withdraws or keeps that GIA is not in this packet."
)
GIP_AS_RULE_RE = re.compile(
    r"(?:(?:will )?deem(?:s|ed)?(?: the IR)? withdrawn )?"
    r"pursuant to Section 3\.6 of the (?:Generator Interconnection Procedures \(GIP\)|GIP)"
    r"(?:, which is referenced but not included in this packet)?"
    r"|deemed withdrawn under (?:Section 3\.6 of )?the GIP"
    r"|withdrawn pursuant to Section 3\.6 of the GIP",
    re.I,
)
GIP_AS_RULE_FIX = (
    "deem the IR withdrawn (BPM-015 r33 §5.4.6). The GIP (Attachment X) is not in this packet"
)
DELAY_ASK_RE = re.compile(
    r"\b7\.3\b|\b7\.7\b|cod delay|commercial operation|"
    r"milestone amendment|ic delay|post-?gia delay",
    re.I,
)
GIA_VOID_DENY_RE = re.compile(
    r"does not (state|say)|do not infer|do not (claim|write)|not say that|"
    r"unless and until",
    re.I,
)


def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def pinned_model() -> str:
    env = (os.environ.get("OPENAI_MODEL") or "").strip()
    if env and env != PINNED_MODEL:
        return PINNED_MODEL
    return PINNED_MODEL


def _mask(text: str) -> str:
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if key and key in text:
        return text.replace(key, "***")
    return text


def _known_cites(packet: dict[str, Any]) -> set[str]:
    known: set[str] = set()
    for u in packet.get("retrieved") or []:
        cite = str(u.get("cite") or "")
        if cite:
            known.add(cite)
        sec = str(u.get("bpm_section") or "")
        if sec.startswith("app"):
            letter = sec.split(".")[-1].upper()
            known.add(f"BPM-015 r33 Appendix {letter}")
        elif sec:
            known.add(f"BPM-015 r33 §{sec}")
    return known


def _packet_for_model(packet: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    slim = json.loads(json.dumps(packet, default=str))
    truncated = False
    for u in slim.get("retrieved") or []:
        text = str(u.get("text") or "")
        if len(text) > MODEL_TEXT_CAP:
            u["text"] = text[:MODEL_TEXT_CAP].rstrip() + "\n..."
            truncated = True
    slim.pop("graph_slice", None)
    slim.pop("search_trace", None)
    return slim, truncated


def _n_sentences(text: str) -> int:
    body = text.strip()
    if not body:
        return 0
    parts = [p for p in SENT_SPLIT.split(body) if p.strip() and not p.strip().startswith("#")]
    return max(len(parts), 1 if body else 0)


def _section_body(md: str, heading: str) -> str:
    pat = re.compile(
        rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\nCompliance:|\Z)",
        re.S | re.M,
    )
    m = pat.search(md)
    return (m.group(1) if m else "").strip()


def _set_section(md: str, heading: str, body: str) -> str:
    block = f"## {heading}\n{body.strip()}\n"
    pat = re.compile(
        rf"^## {re.escape(heading)}\s*\n.*?(?=^## |\nCompliance:|\Z)",
        re.S | re.M,
    )
    if pat.search(md):
        return pat.sub(block + "\n", md, count=1)
    if "Compliance:" in md:
        return md.replace("Compliance:", f"{block}\nCompliance:", 1)
    return md.rstrip() + "\n\n" + block


def _ensure_heading(md: str, shape: str) -> str:
    if shape == "short":
        return md
    if shape == "citation_brief":
        if not md.lstrip().startswith("# Citations only"):
            md = "# Citations only\n\n" + md.lstrip()
        return md
    if not md.lstrip().startswith("# Interconnection procedure note"):
        md = "# Interconnection procedure note\n\n" + md.lstrip()
    return md


def skeleton_from_packet(packet: dict[str, Any], *, dialect: str, error_code: str | None) -> str:
    if error_code in {ZERO_HITS, STUB_ONLY} or not (packet.get("retrieved") or []):
        return sample_zero_hits()
    if dialect == "citation_brief":
        lines = ["# Citations only", "", "The following units were retrieved for this inquiry. No workflow prose is generated in this dialect.", "", "## Citations"]
        for u in packet.get("retrieved") or []:
            pages = u.get("pages") or []
            page_s = f"(pages {pages[0]}-{pages[-1]})" if pages else ""
            lines.append(f"- {u.get('cite')} - {u.get('title')} {page_s}".rstrip())
        lines += ["", "## Gaps"]
        gaps = packet.get("gaps") or []
        if not gaps:
            lines.append("- None recorded by the planner.")
        elif len(gaps) == 1:
            lines.append(gaps[0] if gaps[0].startswith("- ") else f"- {gaps[0]}")
        else:
            for g in gaps:
                lines.append(g if str(g).startswith("- ") else f"- {g}")
        lines += ["", "Compliance: not_determined.", ""]
        return "\n".join(lines)
    retrieved = packet.get("retrieved") or []
    titles = "; ".join(f"{u.get('cite')} {(u.get('title') or '')}".strip() for u in retrieved[:4])
    sit = (
        "The inquiry concerns procedure in the retrieved BPM-015 r33 units. "
        "This note restates those units. It is not a legal opinion. "
        "It does not score compliance of a commercial operation date slip."
    )
    wf_bits = []
    for u in retrieved[:3]:
        title = u.get("title") or "procedure"
        cite = u.get("cite") or "BPM-015 r33"
        wf_bits.append(f"The retrieved unit {cite} addresses {title}.")
    if len(wf_bits) < 2:
        wf_bits.append("MISO and the Interconnection Customer shall follow the cited sections as written.")
    wf = " ".join(wf_bits) + f" Source units include {titles}."
    actors = [s.get("actor") for s in (packet.get("stakeholders") or []) if s.get("actor")]
    if len(actors) >= 3:
        sh = "\n".join(
            f"- The actor `{a}` appears in the retrieved units and has duties stated there."
            for a in actors
        )
    else:
        sh = (
            "The Interconnection Customer, MISO, and the Transmission Owner act as named in the retrieved units. "
            "Duties are not expanded beyond those units."
        )
    cites = []
    for u in retrieved:
        pages = u.get("pages") or []
        page_s = f"(pages {pages[0]}-{pages[-1]})" if pages else ""
        cites.append(f"- {u.get('cite')} - {u.get('title')} {page_s}".rstrip())
    gaps = packet.get("gaps") or []
    if not gaps:
        gap_body = "No additional planner gaps were recorded."
    elif len(gaps) == 1:
        gap_body = gaps[0]
    else:
        gap_body = "\n".join(g if str(g).startswith("- ") else f"- {g}" for g in gaps)
    bans = packet.get("do_not_claim") or DO_NOT_CLAIM
    ban_lines = "\n".join(b if str(b).startswith("- ") else f"- {b}" for b in bans)
    return (
        "# Interconnection procedure note\n\n"
        f"## Situation\n{sit}\n\n"
        f"## Workflow\n{wf}\n\n"
        f"## Stakeholders\n{sh}\n\n"
        "## Citations\n"
        + ("\n".join(cites) if cites else "")
        + "\n\n"
        f"## Gaps\n{gap_body}\n\n"
        "## Must not claim\n"
        f"{ban_lines}\n\n"
        "Compliance: not_determined.\n"
    )


def _chat(messages: list[dict[str, str]], *, json_mode: bool = False) -> tuple[str, dict[str, Any]]:
    _load_env()
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise BotError(OPENAI_MISSING_KEY, "OPENAI_API_KEY is not set")
    body: dict[str, Any] = {
        "model": PINNED_MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    delays_429 = [2.0, 4.0, 8.0]
    transient_left = 2
    rate_i = 0
    while True:
        req = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=COMPOSE_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            text = (
                (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
            )
            usage = data.get("usage") or {}
            return text, {"usage": usage, "model": data.get("model") or PINNED_MODEL}
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            err_body = _mask(err_body)
            if exc.code == 401:
                raise BotError(OPENAI_AUTH, "OpenAI rejected the API key (401).") from exc
            if exc.code == 429:
                if rate_i < len(delays_429):
                    time.sleep(delays_429[rate_i])
                    rate_i += 1
                    continue
                raise BotError(OPENAI_RATE_LIMIT, "OpenAI rate limit (429) after retries.") from exc
            lowered = err_body.lower()
            if exc.code in {400, 404} and (
                "model" in lowered
                and ("does not exist" in lowered or "invalid" in lowered or "not found" in lowered)
            ):
                raise BotError(OPENAI_BAD_MODEL, "Pinned model gpt-4.1 was rejected by the API.") from exc
            if exc.code >= 500:
                if transient_left > 0:
                    transient_left -= 1
                    time.sleep(2.0)
                    continue
                raise BotError(OPENAI_TIMEOUT, f"OpenAI {exc.code} after retries.") from exc
            raise BotError(OPENAI_BAD_MODEL, f"OpenAI HTTP {exc.code}: {err_body[:300]}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if transient_left > 0:
                transient_left -= 1
                time.sleep(2.0)
                continue
            raise BotError(OPENAI_TIMEOUT, "OpenAI timeout after retries.") from exc


def diagram_allowed(shape: str, wants_diagram: bool = False) -> bool:
    """Standard/long notes may carry a compact conceptual map. Short replies do not."""
    if shape in {"short", "citation_brief"}:
        return False
    return bool(wants_diagram or shape in {"standard", "long", "diagram"})


def extract_mermaid(markdown: str) -> str | None:
    m = MERMAID_FENCE.search(markdown or "")
    return m.group(1).strip() if m else None


def _mermaid_label(text: str, n: int = 42) -> str:
    s = DASH_RE.sub(" - ", str(text or ""))
    s = s.replace('"', "'").replace("[", "(").replace("]", ")")
    s = " ".join(s.split())
    return s[:n].rstrip() or "step"


def conceptual_mermaid(packet: dict[str, Any], markdown: str | None = None) -> str:
    """Simple flowchart from units actually used in the note. No style/click."""
    retrieved = [u for u in (packet.get("retrieved") or []) if u.get("cite") or u.get("title")]
    used = set(CITE_RE.findall(markdown or ""))
    units: list[dict[str, Any]] = []
    if used:
        for u in retrieved:
            sec = str(u.get("bpm_section") or "")
            cite = str(u.get("cite") or "")
            if sec in used or any(f"§{sec_n}" in cite for sec_n in used):
                units.append(u)
    if not units:
        return ""
    units = units[:6]
    lines = ["```mermaid", "flowchart TD", '  ask["Current ask"]']
    ids: list[str] = ["ask"]
    for i, u in enumerate(units):
        nid = f"u{i}"
        cite = str(u.get("cite") or "").replace("BPM-015 r33 ", "")
        title = _mermaid_label(u.get("title") or cite, 36)
        label = _mermaid_label(f"{cite} {title}".strip(), 48)
        lines.append(f'  {nid}["{label}"]')
        ids.append(nid)
    chain = " --> ".join(ids)
    lines.append(f"  {chain}")
    lines.append("```")
    return "\n".join(lines)


def _write_system(shape: str, wants_diagram: bool, *, about_study: bool = False) -> str:
    if about_study:
        extra = (
            "A procedure study is already pinned. Answer only the new question from pinned_study "
            "and the retrieved units. Do not rewrite the study. Do not add Situation, Workflow, "
            "Stakeholders, or a Procedure map. Two to five sentences. Pronouns refer to the pinned study."
        )
    elif diagram_allowed(shape, wants_diagram):
        extra = (
            "Include a ## Procedure map with a mermaid flowchart (TD or LR). "
            "Use 4 to 8 nodes, camelCase IDs, quoted labels, no style or click. "
            "Keep the map simple: who acts, then the clock or deposit, then the next actor. "
            "One prose paragraph after the fence. The diagram conceptualizes the current ask. "
            "It does not replace Workflow."
        )
    else:
        extra = "Do not include a mermaid block or a Procedure map heading."
    return (
        writer_pack(shape)
        + "\n\nUse only retrieved units and the conversation history. "
        "History is inline context. Pronouns (that, those, the same IR, the last note) refer to prior turns. "
        "Missing facts go under Gaps. Do not invent section numbers.\n"
        f"Write response_shape `{shape}`.\n"
        + extra
        + "\nCite in the body only the units that answer the current ask. Citations list those same units, not every retrieved neighbor.\n"
        "If this is a follow-up, do not repeat the entire prior note. Answer the new ask and cite.\n"
        "If D2 or the DPP Study Funding Deposit is asked, name BPM-015 r33 §4.2.4.5 in the D2 track. "
        "Do not cite §6.2.11 for D2; §6.2.11 is M2/M3/M4 only.\n"
        "If asked who funds a restudy, cite remaining study deposit or additional deposit as noticed (BPM-015 r33 §5.4.6). "
        "Do not cite §4.2.4.5 as the restudy funding source. D2 is a different deposit track.\n"
        "When reading Platinum 3 flags, do not cite §7.3 or §7.7 as if the flag creates that duty. "
        "Cite delay/COD sections only in a track that asked for IC delay, milestone amendment, or §7.3.\n"
        "If the card or history shows GIA or IA executed, do not infer that missing a restudy notice terminates that GIA "
        "or that BPM-015 r33 §7.3 stops applying. Deemed withdrawal of the IR under §5.4.6 is not GIA termination. "
        "Do not write 'pursuant to Section 3.6 of the GIP' as a retrieved rule. GIP / Attachment X stay under Gaps.\n"
        "If the user combines two analyses (risk card vs BPM, restudy vs D2, restudy vs COD delay, "
        "site control vs restudy), use numbered headings for each track. Do not collapse them into one rule. "
        "Platinum 3 flags, CatBoost P(quit), and delayed-MW pile are not BPM duties. "
        "Answer every track the paragraph named. History is inline context for pronouns and 'the last note'.\n"
        "If gold_stack is attached, open with a Risk results track that quotes CatBoost P(quit 12m) "
        "and Platinum 2 delayed MW using how_to_use. Name the quit model CatBoost, never Electrum. "
        "Never quote Platinum 1 months of COD slip. Scenario delta is a sensitivity. "
        "Stub risks (developer_serial_quit, hazard_exposure, policy_incentive) stay under Gaps.\n"
    )


FOLLOWUP_RE = re.compile(
    r"\b(that|those|the same|this same|you (just )?said|as above|and if|what if they|"
    r"who pays|who funds that|how many (business )?days|same section|from the last|"
    r"from history|still apply|from that last|the last note|does (section|§))\b",
    re.I,
)
SHORT_ASK_RE = re.compile(r"^(who|what is|what are|does |when |how many|can |is |do they)\b", re.I)
LONG_ASK_RE = re.compile(
    r"\b(walk through|explain|step by step|procedure map|who does what|full note|"
    r"two tracks|in one note|combin(e|ing)|compare|contrast|overlay|versus|\bvs\.?\b|"
    r"risk card|as well as|alongside|in addition)\b",
    re.I,
)
CITE_ASK_RE = re.compile(r"\b(which section|cite|citation|where in the bpm)\b", re.I)
NAMED_SEEDS: list[tuple[str, str]] = [
    (r"\bD2\b|study funding deposit", "bpm015-r33::4.2.4.5"),
    (r"decision point ii|\bdp[\s-]?ii\b|\bdecision point 2\b", "bpm015-r33::5.3.3"),
    (r"\bM3\b|\bM4\b", "bpm015-r33::6.2.11"),
    (r"\bsite control\b", "bpm015-r33::5.1.2"),
    (r"\bsuspension\b|\bforce majeure\b", "bpm015-r33::7.1"),
    (r"\b7\.3\b|section 7\.3", "bpm015-r33::7.3"),
    (r"\b7\.7\b|commercial operation", "bpm015-r33::7.7"),
    (r"\bcontour\b|\bgrouping\b", "bpm015-r33::4.3"),
]


def heuristic_plan(
    question: str,
    session: dict[str, Any] | None = None,
    *,
    dialect: str | None = None,
    forced_shape: str | None = None,
) -> dict[str, Any]:
    """Code planner used when gpt-4.1 is skipped or as a floor under the model plan."""
    q = (question or "").strip()
    held = held_catalog(session)
    held_ids = held_unit_ids(session)
    lex = extract_tags(q) if q else {}
    lex_topics = set(lex.get("topic") or [])
    lex_risks = set(lex.get("risk_code") or [])
    overlap_ids: list[str] = []
    for row in held:
        topics = set(row.get("topics") or [])
        risks = set(row.get("risk_code") or [])
        if (lex_topics and topics & lex_topics) or (lex_risks and risks & lex_risks):
            overlap_ids.append(row["unit_id"])
    if not overlap_ids and held_ids and FOLLOWUP_RE.search(q):
        overlap_ids = list(held_ids)
    held_topics = set()
    held_miles = set()
    for row in held:
        held_topics |= set(row.get("topics") or [])
        held_miles |= set(row.get("milestones") or [])
    missing_topics = lex_topics - held_topics
    missing_miles = set(lex.get("milestone") or []) - held_miles
    held_set = set(held_ids)
    missing_named = [
        uid for pat, uid in NAMED_SEEDS if re.search(pat, q, re.I) and uid not in held_set
    ]
    first_turn = not ((session or {}).get("turns") or [])
    n_named = sum(1 for pat, _uid in NAMED_SEEDS if re.search(pat, q, re.I))
    paragraph = len(q) >= 240 or q.count(". ") >= 2
    if missing_named or missing_miles:
        need_search = True
    elif first_turn or not q:
        need_search = True
    elif forced_shape == "citation_brief" and overlap_ids:
        need_search = False
    elif held_ids:
        need_search = False
    else:
        need_search = True
    shape = "standard"
    if forced_shape and forced_shape != "auto":
        shape = normalize_shape(forced_shape, dialect)
    elif CITE_ASK_RE.search(q) and not paragraph and n_named <= 1:
        shape = "citation_brief"
    elif "diagram" in q.lower() or "procedure map" in q.lower() or "who does what" in q.lower():
        shape = "diagram"
    elif LONG_ASK_RE.search(q) or paragraph or n_named >= 2:
        shape = "long"
    elif (not first_turn and FOLLOWUP_RE.search(q) and len(q) < 180):
        shape = "short"
    elif len(q) < 90 and SHORT_ASK_RE.search(q):
        shape = "short"
    elif dialect in {"bpm_register", "long"}:
        shape = "long"
    want_diagram = shape in {"diagram", "long", "standard"}
    if need_search:
        reuse = overlap_ids
    else:
        reuse = list(dict.fromkeys(overlap_ids + held_ids))
    return {
        "need_search": need_search,
        "reuse_unit_ids": reuse,
        "search_focus": q,
        "response_shape": shape,
        "want_diagram": want_diagram,
        "reason": "heuristic: first turn"
        if first_turn
        else "heuristic: named seed missing"
        if missing_named
        else "heuristic: history overlap"
        if overlap_ids
        else "heuristic: new topic",
        "source": "heuristic",
    }


def _planner_system() -> str:
    return (
        "You plan one turn of a MISO BPM-015 procedure bot. Return JSON only. "
        "Keys: need_search (bool), reuse_unit_ids (list of ids from held_units only), "
        "search_focus (short string), response_shape (short|standard|long|citation_brief|diagram), "
        "want_diagram (bool), reason (one sentence). "
        "need_search is false when held_units and history already contain the clause the user is asking about, "
        "including pronoun follow-ups (that, those, the same IR, still apply, from the last note). "
        "need_search is true for a new BPM topic or milestone not in held_units. "
        "need_search is false when the only missing piece is GIP / Attachment X / Section 3.6 of the GIP; that tariff is never in this index. "
        "CatBoost P(quit) and Platinum 2 delayed MW in gold_stack are context; they do not by themselves require a new search. "
        "Do not invent unit ids. Paragraphs that combine two analyses (risk card vs BPM, restudy vs D2, "
        "restudy vs COD delay) use response_shape long, or diagram if they asked for a procedure map. "
        "short = 2-5 sentences only for a narrow follow-up. standard = situation+workflow. "
        "long = full procedure note with a heading per track. citation_brief = citations only. "
        "want_diagram is true for standard, long, and diagram so the note can include a compact conceptual flowchart. "
        "want_diagram is false for short and citation_brief. "
        "Follow-ups like 'who pays for that' reuse the last units. "
        "Do not plan to quote GIP section 3.6 as a retrieved BPM unit."
    )


def plan_query(
    question: str,
    session: dict[str, Any] | None = None,
    *,
    dialect: str | None = None,
    card: dict[str, Any] | None = None,
    gold_stack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pass 1: decide search vs reuse and the answer shape. One gpt-4.1 JSON call."""
    _load_env()
    forced = None
    req_dialect = dialect
    floor = heuristic_plan(question, session, dialect=req_dialect, forced_shape=forced)
    brief = gold_stack_for_model(gold_stack)
    payload = {
        "question": question,
        "history": history_for_model(session),
        "held_units": held_catalog(session),
        "has_card": bool(card),
        "card": {
            "project_key": (card or {}).get("project_key"),
            "study_phase": (card or {}).get("study_phase"),
            "risks": [r.get("code") for r in ((card or {}).get("risks") or [])],
        }
        if card
        else None,
        "gold_stack": brief,
        "allowed_shapes": ["short", "standard", "long", "citation_brief", "diagram"],
    }
    t0 = time.perf_counter()
    try:
        raw, meta = _chat(
            [
                {"role": "system", "content": _planner_system()},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            json_mode=True,
        )
        parsed = json.loads(raw)
        held = set(held_unit_ids(session))
        reuse = [uid for uid in (parsed.get("reuse_unit_ids") or []) if uid in held]
        shape = normalize_shape(parsed.get("response_shape"), dialect)
        floor_shape = floor.get("response_shape") or "standard"
        if floor_shape == "diagram":
            shape = "diagram"
        elif floor_shape == "long" and shape in {"short", "standard", "citation_brief"}:
            shape = "long"
        if floor.get("need_search"):
            need = True
        elif not held:
            need = True
        else:
            # Floor already checked named BPM seeds. Do not search for GIP-only holes.
            need = False
            if not reuse:
                reuse = [uid for uid in (floor.get("reuse_unit_ids") or []) if uid in held]
            if not reuse:
                reuse = list(held)
        plan = {
            "need_search": need,
            "reuse_unit_ids": reuse,
            "search_focus": parsed.get("search_focus") or question,
            "response_shape": shape,
            "want_diagram": bool(parsed.get("want_diagram")) or shape in {"diagram", "standard", "long"},
            "reason": parsed.get("reason") or floor.get("reason"),
            "source": "gpt-4.1",
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "tokens": meta.get("usage"),
            "model": PINNED_MODEL,
        }
        return plan
    except (BotError, json.JSONDecodeError, TypeError) as exc:
        floor["source"] = "heuristic"
        floor["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        floor["error"] = getattr(exc, "code", type(exc).__name__)
        return floor


def first_empty(session: dict[str, Any] | None) -> bool:
    return not held_unit_ids(session)


def compose(
    packet: dict[str, Any],
    *,
    dialect: str | None = None,
    shape: str | None = None,
    history: list[dict[str, Any]] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pass 2: write the note. Code post-check after. No critic/repair LLM calls."""
    _load_env()
    dialect = dialect or ((packet.get("query") or {}).get("requirements") or {}).get("dialect") or "auto"
    shape = normalize_shape(shape or (plan or {}).get("response_shape"), dialect)
    wants = bool((plan or {}).get("want_diagram") or packet.get("wants_diagram") or shape == "diagram")
    about_study = str((packet.get("query") or {}).get("mode") or (plan or {}).get("mode") or "") == "chat"
    if about_study:
        shape = "short"
        wants = False
    error_code = packet.get("error_code")
    passes: list[dict[str, Any]] = []
    mode = "gpt-4.1"
    draft = ""
    compose_error = None

    if error_code in {ZERO_HITS, STUB_ONLY}:
        md, flags, invented = post_check(
            sample_zero_hits(), packet, dialect=dialect, wants_diagram=False, shape="standard"
        )
        return {
            "markdown": md,
            "dialect": dialect,
            "shape": shape,
            "model": PINNED_MODEL,
            "compose_mode": "fallback",
            "passes": [{"name": "code_postcheck", "ok": True, "elapsed_ms": 0, "flags": flags}],
            "plan": plan,
            "error_code": error_code,
            "ok": True,
            "invented_cites": invented,
        }

    slim, truncated = _packet_for_model(packet)
    if truncated:
        compose_error = PACKET_TOO_LARGE

    must_name = []
    qtext = str((packet.get("query") or {}).get("question") or "")
    for u in packet.get("retrieved") or []:
        cite = u.get("cite")
        uid = str(u.get("unit_id") or "")
        if not cite:
            continue
        if uid.endswith("5.4.6") and re.search(r"restud", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("4.2.4.5") and re.search(r"\bD2\b|study funding", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("5.3.3") and re.search(r"decision point ii|\bdp[\s-]?ii\b", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("7.3") and re.search(r"7\.3|milestone amendment|IC delay|post-GIA delay", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("7.7") and re.search(r"7\.7|commercial operation", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("6.2.11") and re.search(r"\bM3\b|\bM4\b", qtext, re.I):
            must_name.append(cite)
        if uid.endswith("5.1.2") and re.search(r"site control", qtext, re.I):
            must_name.append(cite)
    must_name = list(dict.fromkeys(must_name))

    user_blob = json.dumps(
        {
            "question": (packet.get("query") or {}).get("question"),
            "response_shape": shape,
            "history": history or [],
            "gaps": packet.get("gaps"),
            "do_not_claim": packet.get("do_not_claim"),
            "retrieved": slim.get("retrieved"),
            "must_name_cites": must_name,
            "workflow": slim.get("workflow"),
            "stakeholders": slim.get("stakeholders"),
            "card": {
                "project_key": (slim.get("card") or {}).get("project_key"),
                "study_phase": (slim.get("card") or {}).get("study_phase"),
                "observation_date": (slim.get("card") or {}).get("observation_date"),
                "scenario": (slim.get("card") or {}).get("scenario"),
                "flags": (slim.get("card") or {}).get("flags"),
                "risks": [
                    {"code": r.get("code"), "severity": r.get("severity")}
                    for r in ((slim.get("card") or {}).get("risks") or [])
                ],
            },
            "gold_stack": gold_stack_for_model(packet.get("gold_stack") or slim.get("gold_stack")),
            "mode": (packet.get("query") or {}).get("mode") or (plan or {}).get("mode"),
            "pinned_study": ((packet.get("query") or {}).get("pinned_study") or "")[:6000],
        },
        ensure_ascii=False,
        default=str,
    )

    try:
        t0 = time.perf_counter()
        draft, meta = _chat(
            [
                {"role": "system", "content": _write_system(shape, wants, about_study=about_study)},
                {"role": "user", "content": user_blob},
            ]
        )
        passes.append(
            {
                "name": "write",
                "ok": True,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
                "tokens": meta.get("usage"),
                "model": PINNED_MODEL,
            }
        )
    except BotError as exc:
        if exc.code in {OPENAI_MISSING_KEY, OPENAI_TIMEOUT}:
            draft = skeleton_from_packet(packet, dialect="citation_brief" if shape == "citation_brief" else "bpm_register", error_code=error_code)
            mode = "fallback"
            passes.append({"name": "write", "ok": False, "elapsed_ms": 0, "error": exc.code})
            compose_error = exc.code
        else:
            raise

    t0 = time.perf_counter()
    md, flags, invented = post_check(draft, packet, dialect=dialect, wants_diagram=wants, shape=shape)
    passes.append(
        {
            "name": "code_postcheck",
            "ok": True,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "flags": flags,
            "model": PINNED_MODEL,
        }
    )
    return {
        "markdown": md,
        "dialect": dialect,
        "shape": shape,
        "model": PINNED_MODEL,
        "compose_mode": mode,
        "passes": passes,
        "plan": plan,
        "error_code": compose_error,
        "ok": True,
        "invented_cites": invented,
    }


def _prose_for_cites(md: str) -> str:
    return re.sub(
        r"^## Citations\s*\n.*?(?=^## |\nCompliance:|\Z)",
        "",
        md or "",
        flags=re.S | re.M,
    )


def _citation_lines(md: str, retrieved: list[dict[str, Any]]) -> list[str]:
    prose = _prose_for_cites(md)
    used_secs = set(CITE_RE.findall(prose))
    lines: list[str] = []
    seen: set[str] = set()
    for u in retrieved:
        cite = str(u.get("cite") or "")
        sec = str(u.get("bpm_section") or "")
        if not sec:
            m = re.search(r"§(\d+(?:\.\d+)*)", cite)
            sec = m.group(1) if m else ""
        if sec and sec not in used_secs:
            if not re.search(rf"§{re.escape(sec)}(?!\.?\d)", prose):
                continue
        key = cite or u.get("unit_id")
        if not key or key in seen:
            continue
        seen.add(str(key))
        pages = u.get("pages") or []
        page_s = f"(pages {pages[0]}-{pages[-1]})" if pages else ""
        lines.append(f"- {cite} - {u.get('title')} {page_s}".rstrip())
    return lines


def _normalize_gap(item: str) -> str | None:
    g = (item or "").strip().lstrip("- ").strip()
    if not g:
        return None
    low = g.lower()
    if "gip" in low or "attachment x" in low:
        return GIP_NOTE
    if "serial" in low or "developer_serial" in low:
        return "developer_serial_quit has no BPM-015 clause"
    if "fema" in low or "hazard_exposure" in low or "hazard exposure" in low:
        return "hazard_exposure has no BPM-015 clause"
    if "ira" in low or "energy-community" in low or "policy_incentive" in low:
        return "policy_incentive has no BPM-015 clause"
    if "system_congestion" in low or "no unit kept for lexicon risk system" in low:
        return None
    if "no unit kept for lexicon" in low:
        return None
    if g == HONEST_GIA:
        return HONEST_GIA
    return g


def _dedupe_gaps(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        g = _normalize_gap(raw)
        if not g:
            continue
        key = g.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    return out


def _line_claims_gia_void(line: str) -> bool:
    if not GIA_VOID_RE.search(line):
        return False
    return not GIA_VOID_DENY_RE.search(line)


def _rewrite_mix_cites(md: str, question: str) -> str:
    md = GIP_AS_RULE_RE.sub(GIP_AS_RULE_FIX, md)
    md = re.sub(
        r"\(BPM-015 r33 §5\.4\.6,\s*BPM-015 r33 §4\.2\.4\.5\)",
        "(BPM-015 r33 §5.4.6)",
        md,
        flags=re.I,
    )
    md = re.sub(
        r"(funds? the restudy[^.!?\n]{0,200}?)BPM-015 r33 §4\.2\.4\.5",
        r"\1BPM-015 r33 §5.4.6",
        md,
        flags=re.I,
    )
    md = re.sub(
        r"\(BPM-015 r33 §5\.4\.6;\s*§4\.2\.4(?!\.\d)\)",
        "(BPM-015 r33 §5.4.6)",
        md,
        flags=re.I,
    )
    md = re.sub(
        r"\(BPM-015 r33 §5\.4\.6,\s*§4\.2\.4(?!\.\d)\)",
        "(BPM-015 r33 §5.4.6)",
        md,
        flags=re.I,
    )
    md = re.sub(
        r"(\bD2\b[^.!?\n]{0,240})BPM-015 r33 §6\.2\.11",
        r"\1BPM-015 r33 §4.2.4.5",
        md,
        flags=re.I,
    )
    md = re.sub(
        r"(\bD2\b[^.!?\n]{0,240}),\s*§6\.2\.11",
        r"\1, BPM-015 r33 §4.2.4.5",
        md,
        flags=re.I,
    )
    if not DELAY_ASK_RE.search(question or ""):
        md = re.sub(r"\s*\(BPM-015 r33 §7\.[37]\)", "", md)
        md = re.sub(
            r"[^.!?\n]{0,180}BPM-015 r33 §7\.[37][^.!?\n]*[.!?]?",
            " The Platinum 3 flags do not create a BPM-015 delay duty.",
            md,
        )
    return md


def _rewrite_gia_void_lines(md: str) -> tuple[str, bool]:
    if not any(_line_claims_gia_void(ln) for ln in md.splitlines()):
        return md, False
    lines_g: list[str] = []
    inserted = False
    for line in md.splitlines(keepends=True):
        if _line_claims_gia_void(line):
            if not inserted:
                lines_g.append(HONEST_GIA + ("\n" if line.endswith("\n") else ""))
                inserted = True
            continue
        lines_g.append(line)
    return "".join(lines_g), True


def post_check(
    markdown: str,
    packet: dict[str, Any],
    *,
    dialect: str = "bpm_register",
    wants_diagram: bool = False,
    shape: str | None = None,
) -> tuple[str, list[str], list[str]]:
    flags: list[str] = []
    shape = normalize_shape(shape, dialect)
    md = DASH_RE.sub(" - ", markdown or "")
    md = md.replace("!", ".")
    md = EMOJI_RE.sub("", md)
    md = _ensure_heading(md, shape)
    h1 = 0
    kept_h1: list[str] = []
    for ln in md.splitlines(keepends=True):
        if re.match(r"^# [^#]", ln):
            h1 += 1
            if h1 > 1:
                continue
        kept_h1.append(ln)
    md = "".join(kept_h1)
    qtext = str((packet.get("query") or {}).get("question") or "")
    md = _rewrite_mix_cites(md, qtext)
    md, voided = _rewrite_gia_void_lines(md)
    if voided:
        flags.append("gia_termination_inferred")
    for heading in ("Situation", "Workflow", "Stakeholders", "Procedure map"):
        body = _section_body(md, heading)
        if not body:
            continue
        cleaned = body
        for phrase in BANNED_PHRASES:
            if phrase in cleaned.lower():
                flags.append("banned_phrase")
                cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.I)
        if cleaned != body:
            md = _set_section(md, heading, cleaned)
    known = _known_cites(packet)
    invented: list[str] = []
    kept_lines = []
    for line in md.splitlines(keepends=True):
        cites = [f"BPM-015 r33 §{m}" for m in CITE_RE.findall(line)]
        apps = [f"BPM-015 r33 Appendix {m}" for m in APP_CITE_RE.findall(line)]
        bad = [c for c in cites + apps if c not in known]
        if bad:
            invented.extend(bad)
            flags.append(INVENTED_CITE)
            continue
        kept_lines.append(line)
    md = "".join(kept_lines)
    if invented:
        extra = "Invented cites were dropped: " + ", ".join(dict.fromkeys(invented)) + "."
        gaps_now = _section_body(md, "Gaps")
        if extra not in gaps_now:
            md = _set_section(md, "Gaps", (gaps_now + "\n- " + extra).strip() if gaps_now else "- " + extra)

    if re.search(r"\bgip\b|\battachment x\b|section 3\.6 of the gip", md, re.I):
        if "not in this packet" not in md.lower():
            gaps_now = _section_body(md, "Gaps")
            add = GIP_NOTE
            md = _set_section(md, "Gaps", (gaps_now + "\n- " + add).strip() if gaps_now else "- " + add)

    if URL_RE.search(md):
        md = URL_RE.sub("(url omitted)", md)
        flags.append("invented_url")

    if shape in {"standard", "long", "diagram"}:
        sit = _section_body(md, "Situation")
        wf = _section_body(md, "Workflow")
        if sit.lstrip().startswith("- "):
            flags.append("bad_bullet")
            sit = sit.replace("\n- ", " ").lstrip("- ").strip()
            md = _set_section(md, "Situation", sit)
        if wf.lstrip().startswith("- ") and not re.search(r"^\d+\.\s", wf, re.M):
            flags.append("bad_bullet")
            wf = " ".join(line.lstrip("- ").strip() for line in wf.splitlines() if line.strip())
            md = _set_section(md, "Workflow", wf)
        sit = _section_body(md, "Situation")
        wf = _section_body(md, "Workflow")
        numbered = bool(re.search(r"^##\s+\d+", md, re.M))
        enough_prose = numbered or _n_sentences(_prose_for_cites(md)) >= 2
        if _n_sentences(sit) < 2 and not enough_prose:
            flags.append("style_too_short")
            used = set(CITE_RE.findall(md))
            titles = "; ".join(
                (u.get("title") or u.get("cite") or "")
                for u in (packet.get("retrieved") or [])
                if not used
                or str(u.get("bpm_section") or "") in used
                or str(u.get("cite") or "") in md
            )
            md = _set_section(
                md,
                "Situation",
                "The inquiry concerns the retrieved BPM-015 r33 procedure units. "
                f"Those units include {titles or 'the tagged clauses'}. "
                "This note restates the units. It is not a legal opinion.",
            )
        numbered = bool(re.search(r"^##\s+\d+", md, re.M))
        enough_prose = numbered or _n_sentences(_prose_for_cites(md)) >= 2
        if _n_sentences(wf) < 2 and not enough_prose:
            flags.append("style_too_short")
            used = set(CITE_RE.findall(md))
            bits = []
            for u in packet.get("retrieved") or []:
                sec = str(u.get("bpm_section") or "")
                cite = str(u.get("cite") or "")
                if used and sec not in used and cite not in md:
                    continue
                bits.append(f"{cite} addresses {u.get('title')}.")
            if len(bits) < 2:
                bits.append("The Interconnection Customer and MISO shall follow the cited sections.")
            md = _set_section(md, "Workflow", " ".join(bits[:4]))
        for opener in OPENER_BANS:
            body = _section_body(md, "Situation")
            if body.lower().startswith(opener):
                md = _set_section(md, "Situation", body[len(opener) :].lstrip().capitalize())

    allow_map = diagram_allowed(shape, wants_diagram)
    if allow_map and not MERMAID_FENCE.search(md) and (packet.get("retrieved") or []):
        fence_src = conceptual_mermaid(packet, markdown=md)
        if fence_src:
            map_body = (
                fence_src
                + "\n\nThis map restates the retrieved BPM-015 r33 units as a simple sequence. "
                "It does not add duties beyond the citations."
            )
            md = _set_section(md, "Procedure map", map_body)

    fence = MERMAID_FENCE.search(md)
    if fence:
        inner = fence.group(1)
        invalid = False
        if "flowchart" not in inner:
            invalid = True
        if re.search(r"\bstyle\s", inner) or re.search(r"\bclick\s", inner):
            invalid = True
        if re.search(r"\[[^\]]*[\u2013\u2014]", inner):
            invalid = True
        for nid in NODE_ID_RE.findall(inner):
            if " " in nid:
                invalid = True
        after = md[fence.end() :].lstrip()
        next_para = after.split("\n\n", 1)[0].strip() if after else ""
        if not next_para or next_para.startswith("#") or next_para.startswith("```"):
            invalid = True
        if not allow_map:
            invalid = True
        if invalid:
            flags.append(MERMAID_INVALID)
            md = MERMAID_FENCE.sub("", md, count=1)
            md = re.sub(r"^## Procedure map\s*\n+", "", md, flags=re.M)

    # Citations / Must not claim as bullets; force footer from units used in prose.
    retrieved = packet.get("retrieved") or []
    if retrieved:
        md = _set_section(md, "Citations", "\n".join(_citation_lines(md, retrieved)))
    bans = packet.get("do_not_claim") or DO_NOT_CLAIM
    if shape == "short":
        bans = list(bans)[:3]
    md = _set_section(md, "Must not claim", "\n".join(f"- {b.lstrip('- ').strip()}" for b in bans))
    gaps = list(packet.get("gaps") or [])
    md, voided_late = _rewrite_gia_void_lines(md)
    if voided_late:
        flags.append("gia_termination_inferred")
        if HONEST_GIA not in gaps:
            gaps.append(HONEST_GIA)
        if re.search(r"\bgip\b|\battachment x\b|section 3\.6", qtext + md, re.I):
            if GIP_NOTE not in gaps:
                gaps.append(GIP_NOTE)
    elif voided:
        if HONEST_GIA not in gaps:
            gaps.append(HONEST_GIA)
    gap_body = _section_body(md, "Gaps")
    gap_items = [ln.strip().lstrip("- ").strip() for ln in gap_body.splitlines() if ln.strip()]
    for g in gaps:
        gap_items.append(str(g))
    gap_items = _dedupe_gaps(gap_items)
    if not gap_items:
        md = _set_section(md, "Gaps", "No additional planner gaps were recorded.")
    elif len(gap_items) == 1:
        md = _set_section(md, "Gaps", gap_items[0])
    else:
        md = _set_section(md, "Gaps", "\n".join(f"- {it}" for it in gap_items))
    if "Compliance: not_determined" not in md:
        md = md.rstrip() + "\n\nCompliance: not_determined.\n"
    md = re.sub(
        r"(Compliance: not_determined\.\s*)(?:\n+Gaps:[\s\S]*)?$",
        r"\1\n",
        md,
    )
    numbered = bool(re.search(r"^##\s+\d+", md, re.M))
    wf_tail = _section_body(md, "Workflow")
    if numbered and wf_tail and "addresses" in wf_tail:
        md = re.sub(
            r"^## Workflow\s*\n.*?(?=^## |\nCompliance:|\Z)",
            "",
            md,
            flags=re.S | re.M,
        )
    return md.strip() + "\n", list(dict.fromkeys(flags)), list(dict.fromkeys(invented))
