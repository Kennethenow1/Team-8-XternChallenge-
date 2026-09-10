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
    card = slim.get("card") or {}
    for drop in ("p_quit_12m",):
        card.pop(drop, None)
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


def _write_system(shape: str, wants_diagram: bool) -> str:
    extra = (
        "Include a ## Procedure map with a mermaid flowchart (TD or LR) and one prose paragraph after the fence."
        if wants_diagram or shape == "diagram"
        else "Do not include a mermaid block or a Procedure map heading."
    )
    return (
        writer_pack(shape)
        + "\n\nUse only retrieved units and the conversation history. "
        "Missing facts go under Gaps. Do not invent section numbers.\n"
        f"Write response_shape `{shape}`.\n"
        + extra
        + "\nAlways end with Citations (if any units were used), Must not claim, and Compliance: not_determined.\n"
        "If this is a follow-up, do not repeat the entire prior note. Answer the new ask and cite.\n"
    )


FOLLOWUP_RE = re.compile(
    r"\b(that|those|the same|you (just )?said|as above|and if|what if they|who pays|who funds that|"
    r"how many days|same section|from the last|from history)\b",
    re.I,
)
SHORT_ASK_RE = re.compile(r"^(who|what is|what are|does |when |how many|can |is |do they)\b", re.I)
LONG_ASK_RE = re.compile(r"\b(walk through|explain|step by step|procedure map|who does what|full note)\b", re.I)
CITE_ASK_RE = re.compile(r"\b(which section|cite|citation|where in the bpm)\b", re.I)


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
    first_turn = not ((session or {}).get("turns") or [])
    need_search = True
    if forced_shape == "citation_brief" and overlap_ids:
        need_search = False
    elif not first_turn and overlap_ids and not LONG_ASK_RE.search(q):
        need_search = False
    elif not q:
        need_search = True
    shape = "standard"
    if forced_shape and forced_shape != "auto":
        shape = normalize_shape(forced_shape, dialect)
    elif CITE_ASK_RE.search(q):
        shape = "citation_brief"
    elif LONG_ASK_RE.search(q) or "diagram" in q.lower():
        shape = "diagram" if "diagram" in q.lower() or "who does what" in q.lower() else "long"
    elif (not first_turn and FOLLOWUP_RE.search(q)) or (len(q) < 90 and SHORT_ASK_RE.search(q)):
        shape = "short"
    elif dialect in {"bpm_register", "long"}:
        shape = "long"
    want_diagram = shape == "diagram"
    return {
        "need_search": need_search,
        "reuse_unit_ids": overlap_ids or (held_ids if not need_search else []),
        "search_focus": q,
        "response_shape": shape,
        "want_diagram": want_diagram,
        "reason": "heuristic: first turn" if first_turn else "heuristic: history overlap" if overlap_ids else "heuristic: new topic",
        "source": "heuristic",
    }


def _planner_system() -> str:
    return (
        "You plan one turn of a MISO BPM-015 procedure bot. Return JSON only. "
        "Keys: need_search (bool), reuse_unit_ids (list of ids from held_units only), "
        "search_focus (short string), response_shape (short|standard|long|citation_brief|diagram), "
        "want_diagram (bool), reason (one sentence). "
        "need_search is false when held_units and history already contain the clause the user is asking about. "
        "need_search is true for a new topic, a new project card, or when held_units is empty. "
        "Do not invent unit ids. short = 2-5 sentences. standard = situation+workflow. "
        "long = full procedure note. citation_brief = citations only. "
        "Follow-ups like 'who pays for that' reuse the last units."
    )


def plan_query(
    question: str,
    session: dict[str, Any] | None = None,
    *,
    dialect: str | None = None,
    card: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pass 1: decide search vs reuse and the answer shape. One gpt-4.1 JSON call."""
    _load_env()
    forced = None
    req_dialect = dialect
    floor = heuristic_plan(question, session, dialect=req_dialect, forced_shape=forced)
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
        if not held:
            need = True
        else:
            need = bool(parsed.get("need_search"))
            if parsed.get("need_search") is False and reuse:
                need = False
            if not reuse:
                need = True
        plan = {
            "need_search": need,
            "reuse_unit_ids": reuse,
            "search_focus": parsed.get("search_focus") or question,
            "response_shape": shape,
            "want_diagram": bool(parsed.get("want_diagram")) or shape == "diagram",
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

    user_blob = json.dumps(
        {
            "question": (packet.get("query") or {}).get("question"),
            "response_shape": shape,
            "history": history or [],
            "gaps": packet.get("gaps"),
            "do_not_claim": packet.get("do_not_claim"),
            "retrieved": slim.get("retrieved"),
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
        },
        ensure_ascii=False,
        default=str,
    )

    try:
        t0 = time.perf_counter()
        draft, meta = _chat(
            [
                {"role": "system", "content": _write_system(shape, wants)},
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
        if _n_sentences(sit) < 2:
            flags.append("style_too_short")
            titles = "; ".join((u.get("title") or u.get("cite") or "") for u in (packet.get("retrieved") or [])[:3])
            md = _set_section(
                md,
                "Situation",
                "The inquiry concerns the retrieved BPM-015 r33 procedure units. "
                f"Those units include {titles or 'the tagged clauses'}. "
                "This note restates the units. It is not a legal opinion.",
            )
        if _n_sentences(wf) < 2:
            flags.append("style_too_short")
            bits = []
            for u in packet.get("retrieved") or []:
                bits.append(f"{u.get('cite')} addresses {u.get('title')}.")
            if len(bits) < 2:
                bits.append("The Interconnection Customer and MISO shall follow the cited sections.")
            md = _set_section(md, "Workflow", " ".join(bits[:4]))
        for opener in OPENER_BANS:
            body = _section_body(md, "Situation")
            if body.lower().startswith(opener):
                md = _set_section(md, "Situation", body[len(opener) :].lstrip().capitalize())

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
        if shape not in {"diagram"} and not wants_diagram:
            invalid = True
        if invalid:
            flags.append(MERMAID_INVALID)
            md = MERMAID_FENCE.sub("", md, count=1)
            md = re.sub(r"^## Procedure map\s*\n+", "", md, flags=re.M)
        elif not wants_diagram:
            md = MERMAID_FENCE.sub("", md, count=1)

    # Citations / Must not claim as bullets; force footer.
    retrieved = packet.get("retrieved") or []
    cite_body = _section_body(md, "Citations")
    if retrieved:
        needed = []
        for u in retrieved:
            pages = u.get("pages") or []
            page_s = f"(pages {pages[0]}-{pages[-1]})" if pages else ""
            needed.append(f"- {u.get('cite')} - {u.get('title')} {page_s}".rstrip())
        if not cite_body.strip().startswith("- "):
            md = _set_section(md, "Citations", "\n".join(needed))
    bans = packet.get("do_not_claim") or DO_NOT_CLAIM
    if shape == "short":
        bans = list(bans)[:3]
    md = _set_section(md, "Must not claim", "\n".join(f"- {b.lstrip('- ').strip()}" for b in bans))
    gaps = packet.get("gaps") or []
    gap_body = _section_body(md, "Gaps")
    if not gap_body.strip():
        if gaps:
            md = _set_section(
                md,
                "Gaps",
                gaps[0] if len(gaps) == 1 else "\n".join(f"- {g}" for g in gaps),
            )
        else:
            md = _set_section(md, "Gaps", "No additional planner gaps were recorded.")
    elif len(gaps) >= 2 and not gap_body.lstrip().startswith("- "):
        md = _set_section(md, "Gaps", "\n".join(f"- {g.lstrip('- ').strip()}" for g in gaps))
    gap_body = _section_body(md, "Gaps")
    gap_items = [ln.strip().lstrip("- ").strip() for ln in gap_body.splitlines() if ln.strip()]
    if len(gap_items) >= 2:
        md = _set_section(md, "Gaps", "\n".join(f"- {it}" for it in gap_items))
    if "Compliance: not_determined" not in md:
        md = md.rstrip() + "\n\nCompliance: not_determined.\n"
    return md.strip() + "\n", list(dict.fromkeys(flags)), list(dict.fromkeys(invented))
