#!/usr/bin/env python3
"""Write platinum4/02_full_stack_playground.ipynb — saved replies + try your own."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum4" / "02_full_stack_playground.ipynb"
OUT_COPY = REPO / "platinum4" / "results" / "platinum4_full_stack_playground.ipynb"


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
    raise FileNotFoundError("repo root not found; open from the repo or platinum4/")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.modeling.platinum4.gold_stack import (
    DEFAULT_FIXTURE,
    load_full_stack_input,
    queries_from_full_stack,
    risk_code_list,
)
from src.modeling.platinum4.pipeline import run_turn
from src.modeling.platinum4.session import empty_session, load_session, save_session

P4 = REPO / "platinum4" / "results"
ANSWERS = P4 / "answers"
SESSION_PATH = P4 / "sessions" / "playground.json"
SAVED_MD = ANSWERS / "full_stack_conversation.md"
SAVED_JSON = P4 / "full_stack_check.json"

resolved = load_full_stack_input(DEFAULT_FIXTURE)
stack = resolved["gold_stack"]
cb = stack["catboost"]
p2 = stack["platinum2"]
p3 = stack["platinum3"]
proj = stack["project"]

display(Markdown("# Platinum 4 playground — CatBoost stack + gpt-4.1 replies"))
display(Markdown(
    "We already fed **CatBoost** (not Electrum) + Platinum 2 pile + a Platinum 3 "
    f"**{p3.get('scenario')}** card into gpt-4.1. Scroll for the saved notes, then "
    "edit `QUESTION` below and re-run that cell to try your own. **2024 is sealed.**"
))
'''

SCOREBOARD = r'''
display(Markdown("## What we fed the bot"))
display(pd.DataFrame([
    {"slot": "project", "value": f"{proj.get('project_key')} · {proj.get('study_phase')} · {proj.get('capacity_mw')} MW · {proj.get('observation_date')}", "honest_use": "2023 val sample only"},
    {"slot": "scenario", "value": p3.get("scenario"), "honest_use": p3.get("scenario_note")},
    {"slot": "CatBoost P(quit 12m)", "value": cb.get("p_quit_12m"), "honest_use": "ranking, not a BPM trigger"},
    {"slot": "CatBoost under scenario", "value": f"{cb.get('p_quit_under_scenario')} (delta {cb.get('delta_p_quit')})", "honest_use": "sensitivity, not causal"},
    {"slot": "Platinum 2 delayed MW now", "value": p2.get("delayed_mw_now"), "honest_use": "EIA planned pile"},
    {"slot": "Platinum 2 Holt 3m / 12m", "value": f"{p2.get('delayed_mw_h3')} / {p2.get('delayed_mw_h12')}", "honest_use": "history ≤ as-of; not 2024 actuals"},
    {"slot": "GIA-matched delayed MW", "value": p2.get("gia_delayed_mw_now"), "honest_use": "thin overlay, not the full GIA list"},
    {"slot": "BPM-index risks", "value": ", ".join(risk_code_list(p3.get("risks_bpm"))) or "(none)", "honest_use": "procedure units may exist"},
    {"slot": "stub risks", "value": ", ".join(risk_code_list(p3.get("risks_stub"))) or "(none)", "honest_use": "Gaps only"},
]))
display(Markdown("Quit model is **CatBoost** (`catboost_tuned` / trial-149). Not Electrum. Not Platinum 1 delay-months."))
'''

SAVED = r'''
display(Markdown("## Saved gpt-4.1 replies (already run)"))
if not SAVED_MD.exists():
    display(Markdown(
        "_No saved thread. From the repo root run_ "
        "`python scripts/run_platinum4_full_stack.py`."
    ))
else:
    check = json.loads(SAVED_JSON.read_text(encoding="utf-8")) if SAVED_JSON.exists() else {}
    turns = (check.get("turns") or [])
    if turns:
        display(pd.DataFrame([
            {
                "turn": t.get("turn"),
                "id": t.get("id"),
                "searched": t.get("searched"),
                "shape": t.get("shape"),
                "units": ", ".join((t.get("ids") or [])[:4]),
            }
            for t in turns
        ]))
    body = SAVED_MD.read_text(encoding="utf-8")
    parts = [p.strip() for p in body.split("\n---\n") if p.strip()]
    for part in parts[1:]:
        display(Markdown(part))
    display(Markdown(f"_Source: `{SAVED_MD.relative_to(REPO)}`_"))
'''

PLAY = r'''
# --- edit these, then run this cell ---
PROJECT_KEY = "P::B::E291"   # P::B::E291 | P::J2280 | P::J2460
SCENARIO = "restudy"          # baseline | restudy | enter_gia | already_past_cod | rate_shock | serial_developer | high_system_delay
QUESTION = "Does the CatBoost quit score change who funds a restudy after a peer withdrawal?"
RESET_SESSION = False        # True = start a new thread (no history)
# ---------------------------------------

from src.modeling.platinum4.errors import BotError
from src.modeling.platinum4.gold_stack import load_sample_cards, select_card, gold_stack_from_card

card = select_card(load_sample_cards(), PROJECT_KEY, SCENARIO)
stack = gold_stack_from_card(card)
query = {
    "question": QUESTION.strip(),
    "card": card,
    "gold_stack": stack,
    "requirements": {
        "audience": "analyst",
        "dialect": "auto",
        "need": ["workflow", "stakeholders", "citations", "do_not_claim"],
        "max_units": 12,
    },
    "split": "val",
}
session = empty_session() if RESET_SESSION else load_session(SESSION_PATH)
try:
    result = run_turn(query, session)
except BotError as exc:
    display(Markdown(f"**Failed** `{exc.code}`: {exc}"))
else:
    save_session(result["session"], SESSION_PATH)
    composed = result.get("composed") or {}
    md = composed.get("markdown") or ""
    ids = [u.get("unit_id") for u in (result["packet"].get("retrieved") or []) if u.get("unit_id")]
    display(Markdown(
        f"**{PROJECT_KEY}** · `{SCENARIO}` · searched=`{result.get('searched')}` · "
        f"shape=`{composed.get('shape')}` · turns in thread: "
        f"{len((result.get('session') or {}).get('turns') or [])}"
    ))
    display(Markdown(f"Units: `{', '.join(ids) or 'none'}`"))
    display(Markdown(md))
    display(Markdown(f"_Session saved to `{SESSION_PATH.relative_to(REPO)}`. Change QUESTION and re-run for a follow-up._"))
'''

FOLLOW = r'''
# Follow-up on the same thread (uses playground.json from the cell above).
FOLLOWUP = "Who pays for that, and how many Business Days does the IC have?"

from src.modeling.platinum4.errors import BotError
from src.modeling.platinum4.gold_stack import load_sample_cards, select_card, gold_stack_from_card

card = select_card(load_sample_cards(), PROJECT_KEY, SCENARIO)
query = {
    "question": FOLLOWUP.strip(),
    "card": card,
    "gold_stack": gold_stack_from_card(card),
    "requirements": {
        "audience": "analyst",
        "dialect": "auto",
        "need": ["workflow", "citations", "do_not_claim"],
        "max_units": 12,
    },
    "split": "val",
}
session = load_session(SESSION_PATH)
try:
    result = run_turn(query, session)
except BotError as exc:
    display(Markdown(f"**Failed** `{exc.code}`: {exc}"))
except NameError:
    display(Markdown("Run the cell above first so `PROJECT_KEY` / `SCENARIO` exist."))
else:
    save_session(result["session"], SESSION_PATH)
    composed = result.get("composed") or {}
    display(Markdown(
        f"Follow-up searched=`{result.get('searched')}` · shape=`{composed.get('shape')}`"
    ))
    display(Markdown(composed.get("markdown") or "_empty_"))
'''

FOOT = r'''
display(Markdown("## What this is not"))
display(Markdown(
    "- Not Electrum. Quit scores are **CatBoost**.\n"
    "- Not Platinum 1 months of COD slip.\n"
    "- Not a FERC compliance verdict (`compliance` is `not_determined`).\n"
    "- `developer_serial_quit`, `hazard_exposure`, `policy_incentive` have no BPM clause.\n"
    "- Do not pass `split=test`. 2024 stays sealed."
))
display(Markdown(
    "Replay the canned 3-turn thread: `python scripts/run_platinum4_full_stack.py`  \n"
    "Rebuild this notebook: `python scripts/build_platinum4_playground.py`"
))
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_COPY.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        md("# Platinum 4 playground — CatBoost stack + gpt-4.1 replies"),
        md(
            "Open this from the repo root or `platinum4/`. Run All to see the saved "
            "recommendation, then edit `QUESTION` and run that cell to talk to the bot. "
            "Needs `OPENAI_API_KEY` in `.env` for new replies. **2024 test is sealed.**"
        ),
        code(SETUP.strip()),
        md("## What we fed the bot"),
        code(SCOREBOARD.strip()),
        md("## Saved replies"),
        code(SAVED.strip()),
        md("## Try your own question"),
        md(
            "Edit `PROJECT_KEY`, `SCENARIO`, and `QUESTION`, then run the cell. "
            "Set `RESET_SESSION = True` to start over. The next cell is a follow-up "
            "on the same thread."
        ),
        code(PLAY.strip()),
        md("## Follow-up"),
        code(FOLLOW.strip()),
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
