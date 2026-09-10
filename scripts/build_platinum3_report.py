#!/usr/bin/env python3
"""Write platinum3/01_risk_cards.ipynb (Plotly, val cards, no new trainer)."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum3" / "01_risk_cards.ipynb"
OUT_COPY = REPO / "platinum3" / "results" / "platinum3_risk_cards.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


SETUP = r'''
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from IPython.display import Markdown, display

warnings.filterwarnings("ignore", category=FutureWarning)
pio.renderers.default = "plotly_mimetype+notebook"

HERE = Path.cwd().resolve()
REPO = None
for p in [HERE, *HERE.parents]:
    if (p / "platinum3" / "results").exists() and (p / "src" / "gold").exists():
        REPO = p
        break
if REPO is None:
    raise FileNotFoundError("repo root not found")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RESULTS = REPO / "platinum3" / "results"
FIG = RESULTS / "figures"
FIG.mkdir(parents=True, exist_ok=True)
CARDS = RESULTS / "val_risk_cards.parquet"
SAMPLES = RESULTS / "sample_cards.json"
SENS = RESULTS / "scenario_sensitivity.json"
SCHEMA = RESULTS / "schema.json"
AUDIT = RESULTS / "val_card_audit.parquet"

if not CARDS.exists():
    display(Markdown("_Cards missing — building val risk cards now (no new trainer)._"))
    from src.modeling.platinum3.cards import build_risk_cards, write_risk_card_bundle
    write_risk_card_bundle(build_risk_cards(split="val"))

df = pd.read_parquet(CARDS)
summary = json.loads(SENS.read_text(encoding="utf-8")) if SENS.exists() else {}
schema = json.loads(SCHEMA.read_text(encoding="utf-8")) if SCHEMA.exists() else {}
samples = json.loads(SAMPLES.read_text(encoding="utf-8")) if SAMPLES.exists() else []
base = df[df["scenario"].eq("baseline")].copy()

display(Markdown("# Platinum 3 — risk cards for a mitigation bot"))
display(Markdown(
    "Not a fourth contest model. Each row is a **ChatGPT-safe card**: Electrum P(quit), "
    "Platinum 2 delayed-MW pile, gold flags, scenario re-score of the **same** CatBoost."
))
display(Markdown(
    f"Split **{summary.get('split', 'val')}**. "
    f"Projects **{summary.get('n_rows', len(base))}**. "
    f"Cards **{summary.get('n_cards', len(df))}**. "
    f"Scorer **`{summary.get('scorer_source')}`**. "
    f"**Test sealed.**"
))
display(Markdown(f"_{summary.get('calibration_note', '')}_"))
'''

INTRO = r'''
display(Markdown("## What GPT is allowed to see"))
codes = schema.get("risk_codes") or {}
rows = [{"code": k, "meaning": v} for k, v in codes.items()]
display(pd.DataFrame(rows))
display(Markdown("**Do not claim**"))
for line in schema.get("do_not_claim") or []:
    display(Markdown(f"- {line}"))
'''

SENS_PLOT = r'''
sens = pd.DataFrame(summary.get("scenario_sensitivity_val_only") or [])
if len(sens):
    color = ["#1B7F4E" if v > 0 else ("#6B7280" if abs(v) < 1e-9 else "#B42318") for v in sens["mean_delta_p"]]
    fig = go.Figure(go.Bar(x=sens["scenario"], y=sens["mean_delta_p"], marker_color=color, name="mean ΔP(quit)"))
    fig.add_hline(y=0, line_dash="dot", line_color="#9CA3AF")
    fig.update_layout(
        title="Val sensitivity: mean change in P(quit) if that scenario were on the row",
        yaxis_title="mean Δ P(quit)",
        annotations=[dict(
            text="Green = P(quit) up. Red = down. Not causal. Flags still fire.",
            xref="paper", yref="paper", x=0, y=1.12, showarrow=False, font=dict(size=12, color="#6B7280"),
        )],
    )
    fig.write_html(FIG / "scenario_delta.html")
    fig.show()
    display(sens)
else:
    display(Markdown("_No scenario_sensitivity.json — run scripts/run_platinum3_risk_cards.py_"))
'''

DIST = r'''
fig = go.Figure()
fig.add_trace(go.Histogram(x=base["p_quit_12m"], nbinsx=40, marker_color="#2F6FED", name="P(quit 12m)"))
fig.add_vline(x=0.05, line_dash="dash", line_color="#B45309", annotation_text="medium 5%")
fig.add_vline(x=0.10, line_dash="dash", line_color="#B42318", annotation_text="high 10%")
fig.update_layout(title="Baseline P(quit in ~12 months) — 2023 val", xaxis_title="P(quit)", yaxis_title="projects")
fig.write_html(FIG / "p_quit_hist.html")
fig.show()
display(Markdown(
    f"Median P(quit) **{base['p_quit_12m'].median():.3f}**. "
    f"Share ≥5% **{(base['p_quit_12m']>=0.05).mean():.1%}**. "
    f"Share ≥10% **{(base['p_quit_12m']>=0.10).mean():.1%}**."
))
'''

FLAGS = r'''
flag_cols = [c for c in base.columns if c.startswith("flag_")]
rates = (
    pd.Series({c.replace("flag_", ""): float(base[c].mean()) for c in flag_cols})
    .sort_values(ascending=False)
    .reset_index()
)
rates.columns = ["flag", "share_of_val"]
fig = go.Figure(go.Bar(x=rates["flag"], y=rates["share_of_val"], marker_color="#0F766E"))
fig.update_layout(title="How often each flag is on (baseline val)", yaxis_tickformat=".0%")
fig.write_html(FIG / "flag_rates.html")
fig.show()
display(rates)
pile = base[["delayed_mw_now", "delayed_mw_h3", "delayed_mw_h12", "pile_percentile_pit"]].drop_duplicates()
display(Markdown("## System pile on these val dates (Platinum 2, PIT)"))
display(pile)
'''

RENDER = r'''
def show_card(c: dict) -> None:
    sc = (c.get("scenario") or {}).get("name")
    pile = c.get("pile") or {}
    p0 = c.get("p_quit_12m") or 0
    ps = c.get("p_quit_under_scenario") or 0
    d = c.get("delta_p_quit") or 0
    risks = c.get("risks") or []
    bullets = "\n".join(
        f"- **{r.get('severity')}** `{r.get('code')}` — {r.get('evidence')}" for r in risks
    ) or "- _no risk codes_"
    display(Markdown(
        f"### `{c.get('project_key')}` · {sc}\n"
        f"{c.get('capacity_mw')} MW · {c.get('technology_primary')} · {c.get('state_code')} · "
        f"{c.get('study_phase')} · {c.get('observation_date')}\n\n"
        f"**P(quit)** {p0:.1%} → under scenario **{ps:.1%}** (Δ {d:+.1%})\n\n"
        f"Pile now **{pile.get('delayed_mw_now')}** MW · 12m Holt **{pile.get('delayed_mw_h12')}** · "
        f"PIT percentile **{pile.get('pile_percentile_pit')}**\n\n"
        f"{bullets}\n\n"
        f"Playbooks: {', '.join('`'+p+'`' for p in (c.get('playbook_ids') or [])) or '_none_'}"
    ))


display(Markdown("## Sample cards (what you would hand GPT)"))
keys = sorted({c.get("project_key") for c in samples})
display(Markdown("Projects: " + ", ".join(f"`{k}`" for k in keys)))
for c in samples:
    if (c.get("scenario") or {}).get("name") == "baseline":
        show_card(c)
'''

SCENARIO_ONE = r'''
display(Markdown("## Same project, every scenario"))
LOOK = "P::B::E291"
sub = [c for c in samples if c.get("project_key") == LOOK]
if not sub:
    LOOK = (samples[0].get("project_key") if samples else None)
    sub = [c for c in samples if c.get("project_key") == LOOK]
display(Markdown(f"Looking at `{LOOK}`."))
for c in sub:
    show_card(c)
'''

TOP = r'''
display(Markdown("## Highest baseline P(quit) on val (team view)"))
cols = [
    "project_key", "capacity_mw", "study_phase", "p_quit_12m",
    "risk_codes", "flag_is_gia", "flag_cod_already_slipped", "flag_developer_serial", "flag_pile_crowded",
]
show = base.sort_values("p_quit_12m", ascending=False).head(15)
display(show[cols])
if AUDIT.exists():
    audit = pd.read_parquet(AUDIT)
    merged = show.merge(audit[["project_key", "y_true"]], on="project_key", how="left")
    display(Markdown(
        "_`y_true` is **not** on the GPT card. It is here so you can see whether high scores were actual quitters._"
    ))
    display(merged[["project_key", "p_quit_12m", "y_true", "risk_codes"]])
'''

LOOKUP = r'''
# Change this key and re-run the cell.
PROJECT_KEY = base["project_key"].iloc[0]
row = df[df["project_key"].eq(PROJECT_KEY)]
display(Markdown(f"## Lookup `{PROJECT_KEY}`"))
display(row[[
    "scenario", "p_quit_12m", "p_quit_under_scenario", "delta_p_quit",
    "study_phase", "risk_codes",
]])
'''

FOOT = r'''
display(Markdown("## What this is not"))
display(Markdown(
    "- Not a new neural net.\n"
    "- Not months of future COD slip (Platinum 1 failed; do not quote it).\n"
    "- Not a MISO Step-Up failure record.\n"
    "- Scenario ΔP is a sensitivity, not “if restudy then delay = X months.”\n"
    "- BPM citations live in **Platinum 4** (`platinum4/01_bot_packets.ipynb`)."
))
display(Markdown(
    "Rebuild cards: `python scripts/run_platinum3_risk_cards.py`  \n"
    "Rebuild this notebook: `python scripts/build_platinum3_report.py`  \n"
    "Card → citations: `python scripts/build_platinum4_report.py`"
))
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_COPY.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        md("# Platinum 3 — risk cards"),
        md(
            "Val-only view of the mitigation **peripherals**. "
            "Electrum / Platinum 1 / Platinum 2 trainers are untouched. **2024 test is sealed.**"
        ),
        code(SETUP.strip()),
        md("## Contract"),
        code(INTRO.strip()),
        md("## Do scenarios move P(quit)?"),
        code(SENS_PLOT.strip()),
        md("## Quit scores"),
        code(DIST.strip()),
        md("## Flags and pile"),
        code(FLAGS.strip()),
        md("## Cards"),
        code(RENDER.strip()),
        code(SCENARIO_ONE.strip()),
        md("## Top of the list"),
        code(TOP.strip()),
        md("## Look up one project"),
        code(LOOKUP.strip()),
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
