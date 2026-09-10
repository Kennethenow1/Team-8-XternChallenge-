#!/usr/bin/env python3
"""Write platinum2/results/platinum2_performance.ipynb."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum2" / "results" / "platinum2_performance.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


SETUP = r'''
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from IPython.display import Markdown, display

warnings.filterwarnings("ignore", category=FutureWarning)

HERE = Path.cwd().resolve()
REPO = None
for p in [HERE, *HERE.parents]:
    if (p / "platinum2" / "results" / "leaderboard.csv").exists() or (p / "src" / "gold").exists():
        REPO = p
        break
if REPO is None:
    raise FileNotFoundError("repo root not found")

RESULTS = REPO / "platinum2" / "results"
FIG = RESULTS / "figures"
FIG.mkdir(parents=True, exist_ok=True)
GOLD = REPO / "data" / "gold" / "delay" / "platinum2"

lb = pd.read_csv(RESULTS / "leaderboard.csv") if (RESULTS / "leaderboard.csv").exists() else pd.DataFrame()
audit = {}
if (GOLD / "series_audit.json").exists():
    audit = json.loads((GOLD / "series_audit.json").read_text(encoding="utf-8"))
display(Markdown("# Platinum 2 — delayed MW sitting in GIA next year"))
display(Markdown(
    "Not project-row COD months. This is the **stock of delayed megawatts** in the EIA planned inventory. "
    "GIA is a thinner matched overlay. 2024 is sealed."
))
display(Markdown(
    f"Snapshots **{audit.get('n_snapshots')}**. "
    f"Enough for a real series: **{audit.get('enough_for_timesfm')}**."
))
display(lb)
'''

SERIES = r'''
series_path = GOLD / "gia_delayed_mw_monthly.parquet"
if series_path.exists():
    s = pd.read_parquet(series_path)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["year_month"], y=s["delayed_mw"], mode="lines+markers", name="delayed MW (EIA planned)"))
    if "gia_delayed_mw" in s.columns:
        fig.add_trace(go.Scatter(x=s["year_month"], y=s["gia_delayed_mw"], mode="lines+markers", name="GIA-matched delayed MW"))
    fig.update_layout(title="Delayed planned MW over EIA quarters", yaxis_title="MW")
    fig.write_html(FIG / "series.html")
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
else:
    display(Markdown("_series missing — run scripts/run_platinum2_gold.py_"))
'''

LB = r'''
ok = lb[lb["status"].eq("ok")].copy() if len(lb) else lb
if len(ok) and "rmse_h12" in ok.columns:
    fig = go.Figure(go.Bar(x=ok["model"], y=ok["rmse_h12"], name="RMSE h=12m"))
    fig.update_layout(title="12-month-ahead RMSE (MW). Lower is better. Test sealed.")
    fig.write_html(FIG / "rmse_h12.html")
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
if len(ok) and "rmse_h3" in ok.columns:
    fig = go.Figure(go.Bar(x=ok["model"], y=ok["rmse_h3"], name="RMSE h=3m"))
    fig.update_layout(title="3-month-ahead RMSE (sanity)")
    fig.write_html(FIG / "rmse_h3.html")
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
'''

FOOT = r'''
display(Markdown("## What this is not"))
display(Markdown(
    "- Not a per-project COD calendar (that was Platinum 1, and it did not work).\\n"
    "- Not a MISO Firm Service Step-Up failure record.\\n"
    "- EIA planned-COD slip in MISO-footprint states, with a GIA match overlay."
))
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        md("# Platinum 2 performance (val only)"),
        code(SETUP.strip()),
        md("## Series"),
        code(SERIES.strip()),
        md("## Leaderboard"),
        code(LB.strip()),
        code(FOOT.strip()),
    ]
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    OUT.write_text(nbf.writes(nb), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
