#!/usr/bin/env python3
"""Write platinum4/01_bot_packets.ipynb (catalog, search_trace, gpt-4.1 note)."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum4" / "01_bot_packets.ipynb"
OUT_COPY = REPO / "platinum4" / "results" / "platinum4_bot_packets.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


SETUP = r'''
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from IPython.display import Markdown, display

HERE = Path.cwd().resolve()
REPO = None
for p in [HERE, *HERE.parents]:
    if (p / "platinum4" / "results").exists() and (p / "src" / "gold").exists():
        REPO = p
        break
if REPO is None:
    raise FileNotFoundError("repo root not found")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

P3 = REPO / "platinum3" / "results"
P4 = REPO / "platinum4" / "results"
SAMPLES = P3 / "sample_cards.json"
PACKETS = P4 / "sample_bot_packets.json"
ANSWERS = P4 / "answers"
POLICY_INDEX = REPO / "docs" / "miso_policy" / "index"

samples = json.loads(SAMPLES.read_text(encoding="utf-8")) if SAMPLES.exists() else []
packets = json.loads(PACKETS.read_text(encoding="utf-8")) if PACKETS.exists() else []

display(Markdown("# Platinum 4 — catalog, search, gpt-4.1"))
display(Markdown(
    "Not a contest model. Planner tags decide which BPM-015 r33 units to read. "
    "**gpt-4.1** writes the note from those units. **2024 test is sealed.**"
))
'''

CATALOG = r'''
display(Markdown("## Search catalog"))
cat_path = POLICY_INDEX / "search_catalog.json"
if not cat_path.exists():
    display(Markdown("_Missing search_catalog.json. Run `python scripts/build_miso_policy_index.py`._"))
else:
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    display(Markdown(
        f"Doc `{cat.get('doc_id')}` status **{cat.get('status')}**, "
        f"{cat.get('n_units')} units, effective {cat.get('effective_date')}."
    ))
    holes = cat.get("holes") or {}
    display(Markdown(
        f"Holes: stub risks `{', '.join(holes.get('stub_risks') or [])}`. "
        f"Not retrieved: `{', '.join(holes.get('not_retrieved') or [])}`. "
        f"GIQ coarser than DPP 1/2/3: `{holes.get('giq_coarser_than_dpp')}`."
    ))
    shelf_rows = []
    for sh in cat.get("shelves") or []:
        shelf_rows.append({
            "facet": sh.get("facet"),
            "tag": sh.get("tag"),
            "n": sh.get("n"),
            "example": ", ".join(sh.get("example_cites") or [])[:80],
        })
    if shelf_rows:
        counts = pd.DataFrame(shelf_rows).groupby("facet", as_index=False)["n"].sum()
        display(Markdown("### Shelves (unit counts by facet)"))
        display(counts)
    examples = cat.get("query_examples") or []
    if examples:
        display(Markdown("### Canned query routes"))
        display(pd.DataFrame(examples))
'''

GRAPH = r'''
display(Markdown("## Ontology graph"))
gpath = POLICY_INDEX / "ontology_graph.json"
if not gpath.exists():
    display(Markdown("_Missing ontology_graph.json._"))
else:
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    display(Markdown(f"{graph.get('n_nodes')} nodes, {graph.get('n_edges')} edges."))
    kinds = pd.Series([n.get("kind") for n in nodes]).value_counts().rename_axis("kind").reset_index(name="n")
    display(kinds)
    rels = pd.Series([e.get("rel") for e in edges]).value_counts().rename_axis("rel").reset_index(name="n")
    display(rels)
    seed_rows = []
    for e in edges:
        if e.get("rel") == "seed_for":
            seed_rows.append({"unit": e.get("from"), "risk": e.get("to")})
    if seed_rows:
        display(Markdown("### Seed edges (risk map, not every tagged descendant)"))
        display(pd.DataFrame(seed_rows))
'''

CONTRACT = r'''
display(Markdown("## What GPT is allowed to see"))
display(Markdown(
    "Input is a Platinum 3 risk card and/or a question. Retrieval is from "
    "`docs/miso_policy/index/` (r33 clean). Compliance is **not_determined**. "
    "Model is **gpt-4.1** only. Do not send `val_card_audit.parquet`."
))
ont_path = POLICY_INDEX / "ontology.json"
if ont_path.exists():
    ont = json.loads(ont_path.read_text(encoding="utf-8"))
    display(Markdown(
        f"Ontology `{ont.get('schema_version')}`. "
        f"Stub risks (no BPM clause): `{', '.join(ont.get('stub_risks_no_bpm') or [])}`."
    ))
risk_map_path = POLICY_INDEX / "maps" / "risk_code_to_units.json"
if risk_map_path.exists():
    risk_map = json.loads(risk_map_path.read_text(encoding="utf-8"))
    map_rows = []
    for code, entry in risk_map.items():
        map_rows.append({
            "risk_code": code,
            "n_units": len(entry.get("unit_ids") or []),
            "note": entry.get("note") or "BPM-015 clause(s)",
            "unit_ids": ", ".join(entry.get("unit_ids") or []) or "—",
        })
    display(pd.DataFrame(map_rows))
'''

RETRIEVE = r'''
from src.modeling.platinum4.retrieve import retrieve_for_card

if not packets and samples:
    try:
        packets = [retrieve_for_card(c) for c in samples if (c.get("scenario") or {}).get("name") == "baseline"]
    except FileNotFoundError as exc:
        display(Markdown(f"_Index missing: {exc}_"))
        packets = []

display(Markdown("## Card-only retrieval (`retrieve_for_card`)"))
if packets:
    shown = 0
    for pkt in packets:
        card = pkt.get("card") or {}
        if (card.get("scenario") or {}).get("name") not in {"baseline", "restudy"}:
            continue
        if shown >= 6:
            break
        shown += 1
        cites = "\n".join(
            f"- `{r.get('cite')}` — {r.get('title')}" for r in (pkt.get("retrieved") or [])
        ) or "- _none_"
        stakeholders = ", ".join(
            f"`{s.get('actor')}`" for s in (pkt.get("stakeholders") or [])
        ) or "_none_"
        display(Markdown(
            f"### `{card.get('project_key')}` · {(card.get('scenario') or {}).get('name')} · {card.get('study_phase')}\n"
            f"GI phase guess: `{pkt.get('workflow', {}).get('gi_phase_guess')}`\n\n"
            f"Compliance: **{(pkt.get('compliance') or {}).get('status')}** — "
            f"{(pkt.get('compliance') or {}).get('meaning')}\n\n"
            f"Stakeholders: {stakeholders}\n\n"
            f"{cites}"
        ))
else:
    display(Markdown(
        "_No bot packets. Run `python scripts/build_miso_policy_index.py` "
        "(needs Platinum 3 `sample_cards.json`)._"
    ))
'''

QUERY = r'''
from src.modeling.platinum4.errors import BotError
from src.modeling.platinum4.search import retrieve_for_query

display(Markdown("## Card + question (`retrieve_for_query`)"))
LOOK = "P::B::E291"
card = next((c for c in samples if c.get("project_key") == LOOK and (c.get("scenario") or {}).get("name") == "baseline"), None)
question = "Who funds a restudy if a peer withdraws?"
query_pkt = None
try:
    query_pkt = retrieve_for_query({
        "question": question,
        "card": card,
        "requirements": {
            "audience": "analyst",
            "dialect": "bpm_register",
            "need": ["workflow", "stakeholders", "citations", "do_not_claim"],
            "max_units": 12,
        },
    })
except BotError as exc:
    display(Markdown(f"_Query failed `{exc.code}`: {exc}_"))
except FileNotFoundError as exc:
    display(Markdown(f"_Index missing: {exc}_"))

if query_pkt:
    ids = [r.get("unit_id") for r in (query_pkt.get("retrieved") or [])]
    display(Markdown(
        f"Question: **{question}**  \n"
        f"Kept units: `{', '.join(ids) or 'none'}`.  \n"
        f"Gaps: {query_pkt.get('gaps') or []}."
    ))
    trace = query_pkt.get("search_trace") or {}
    alg_rows = []
    for a in trace.get("algorithms") or []:
        alg_rows.append({
            "algorithm": a.get("name"),
            "n": a.get("n_candidates"),
            "top": ", ".join(a.get("top_ids") or [])[:80],
            "ms": a.get("elapsed_ms"),
            "error": a.get("error"),
        })
    display(Markdown("### search_trace.algorithms"))
    display(pd.DataFrame(alg_rows))
    dir_rows = []
    for d in trace.get("directives") or []:
        dir_rows.append({"directive": d.get("name"), "ok": d.get("ok"), "reason": d.get("reason")})
    display(Markdown("### search_trace.directives"))
    display(pd.DataFrame(dir_rows))
    gslice = query_pkt.get("graph_slice") or {}
    display(Markdown(
        f"graph_slice: {len(gslice.get('nodes') or [])} nodes, "
        f"{len(gslice.get('edges') or [])} edges, "
        f"algorithms `{', '.join(gslice.get('algorithms') or [])}`."
    ))
'''

COMPOSE = r'''
from src.modeling.platinum4.compose import PINNED_MODEL, compose

display(Markdown("## Two-pass note (gpt-4.1 plan + write)"))
display(Markdown(f"Pinned model: `{PINNED_MODEL}`. Planner decides search vs history reuse and the answer shape. Writer is one call. Code post-check is not an LLM pass."))
answer_md = None
answer_meta = None
if ANSWERS.exists():
    mds = sorted(ANSWERS.glob("*.md"))
    prefer = [p for p in mds if "restudy" in p.name or "withdraw" in p.name]
    pick = (prefer or mds)
    if pick:
        answer_md = pick[0].read_text(encoding="utf-8")
        js = pick[0].with_suffix(".json")
        if js.exists():
            answer_meta = json.loads(js.read_text(encoding="utf-8"))

if answer_md is None and query_pkt is not None:
    composed = compose(query_pkt, dialect="bpm_register")
    answer_md = composed.get("markdown")
    answer_meta = composed

if answer_md:
    if answer_meta:
        passes = answer_meta.get("passes") or []
        display(Markdown(
            f"compose_mode `{answer_meta.get('compose_mode')}`, "
            f"model `{answer_meta.get('model') or PINNED_MODEL}`."
        ))
        if passes:
            display(pd.DataFrame(passes))
    display(Markdown(answer_md))
else:
    display(Markdown(
        "_No composed note. Run "
        "`python scripts/run_platinum4_answer.py --question \"Who funds a restudy if a peer withdraws?\" --project-key P::B::E291`._"
    ))
'''

FOOT = r'''
display(Markdown("## What this is not"))
display(Markdown(
    "- Not a new neural net.\n"
    "- Not months of future COD slip (Platinum 1 failed; do not quote it).\n"
    "- Not a legal opinion on a COD slip (`compliance` is `not_determined`).\n"
    "- `developer_serial_quit`, `hazard_exposure`, and `policy_incentive` have no BPM clause.\n"
    "- 2024 test labels stay sealed. Packets are 2023 val samples only.\n"
    "- No chat model other than gpt-4.1."
))
display(Markdown(
    "Rebuild cards: `python scripts/run_platinum3_risk_cards.py`  \n"
    "Rebuild index + packets: `python scripts/build_miso_policy_index.py`  \n"
    "Compose a note: `python scripts/run_platinum4_answer.py --question \"Who funds a restudy if a peer withdraws?\" --project-key P::B::E291`  \n"
    "Rebuild this notebook: `python scripts/build_platinum4_report.py`"
))
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_COPY.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        md("# Platinum 4 — catalog, search, gpt-4.1"),
        md(
            "Card and/or question → BPM-015 citations, then a gpt-4.1 procedure note. "
            "**2024 test is sealed.**"
        ),
        code(SETUP.strip()),
        md("## Catalog"),
        code(CATALOG.strip()),
        md("## Ontology graph"),
        code(GRAPH.strip()),
        md("## Contract"),
        code(CONTRACT.strip()),
        md("## Card-only retrieval"),
        code(RETRIEVE.strip()),
        md("## Hybrid search"),
        code(QUERY.strip()),
        md("## Composed note"),
        code(COMPOSE.strip()),
        code(FOOT.strip()),
    ]
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    text = nbf.writes(nb)
    OUT.write_text(text, encoding="utf-8")
    OUT_COPY.write_text(text, encoding="utf-8")
    print("wrote", OUT)
    print("wrote", OUT_COPY)


if __name__ == "__main__":
    main()
