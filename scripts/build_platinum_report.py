#!/usr/bin/env python3
"""Write platinum/results/platinum_performance.ipynb (Plotly, val-only)."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum" / "results" / "platinum_performance.ipynb"


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
import plotly.io as pio
from IPython.display import Markdown, display

warnings.filterwarnings("ignore", category=FutureWarning)
pio.renderers.default = "plotly_mimetype"

HERE = Path.cwd().resolve()
REPO = None
for p in [HERE, *HERE.parents]:
    if (p / "platinum" / "results" / "leaderboard.csv").exists():
        REPO = p
        break
if REPO is None:
    raise FileNotFoundError("platinum/results/leaderboard.csv not found")

RESULTS = REPO / "platinum" / "results"
FIG = RESULTS / "figures"
FIG.mkdir(parents=True, exist_ok=True)
GOLD = REPO / "data" / "gold" / "delay"

lb = pd.read_csv(RESULTS / "leaderboard.csv") if (RESULTS / "leaderboard.csv").exists() else pd.DataFrame()
audit = {}
ap = GOLD / "label_audit.json"
if ap.exists():
    audit = json.loads(ap.read_text(encoding="utf-8"))
display(Markdown("# Platinum — from approved MW to deliverable MW"))
display(Markdown(
    "Val-only COD-slip models. We are **not** claiming a MISO Step-Up failure record; "
    "the process is still proposed. This report measures generator COD execution risk "
    "that a future Firm Service Step-Up increment would revalidate."
))
display(Markdown(
    f"Follow-up window **{audit.get('followup_months', 24)} months**. "
    f"Val labeled **{audit.get('val_labeled')}**. "
    f"Neural nets allowed: **{audit.get('neural_nets_ok')}**."
))
display(lb)
'''

GIA = r'''
panel_path = GOLD / "cod_delay_panel.parquet"
if panel_path.exists():
    panel = pd.read_parquet(panel_path)
    lab = panel[panel["cod_slip_months_next_12m"].notna() & panel["split"].eq("val")].copy()
    if "is_gia" in lab.columns:
        gia = lab[lab["is_gia"].fillna(False)]
    else:
        gia = lab
    slip = pd.to_numeric(gia["cod_slip_months_next_12m"], errors="coerce") if len(gia) else pd.Series(dtype=float)
    mw = pd.to_numeric(gia.get("capacity_mw"), errors="coerce").fillna(0) if len(gia) else pd.Series(dtype=float)
    delayed = slip >= 12
    display(Markdown("## GIA / advanced-study slice (slide 4)"))
    display(Markdown(
        f"Val GIA rows **{len(gia)}**. Median slip **{float(slip.median()) if len(slip) else float('nan'):.1f}** months. "
        f"Share ≥12m **{(delayed.mean() if len(slip) else float('nan')):.1%}**. "
        f"Delayed GIA MW **{float(mw[delayed].sum()) if len(gia) else 0:.0f}**."
    ))
    fig = go.Figure(go.Histogram(x=slip, nbinsx=20, name="val GIA slip"))
    fig.update_layout(title="Val COD slip months — GIA/advanced subset", xaxis_title="months")
    fig.write_html(FIG / "gia_slip.html")
    try:
        fig.write_image(FIG / "gia_slip.png")
    except Exception as e:
        print("png skipped:", e)
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
else:
    display(Markdown("_cod_delay_panel.parquet missing — run scripts/run_delay_gold.py_"))
'''

LB = r'''
ok = lb[lb["status"].isin(["ok", "not_competitive"])].copy() if len(lb) else lb
if len(ok) and "mae" in ok.columns:
    fig = go.Figure(go.Bar(x=ok["model"], y=ok["mae"], name="val MAE"))
    fig.update_layout(title="Val MAE (lower is better). Test sealed.", yaxis_title="months")
    fig.write_html(FIG / "mae_leaderboard.html")
    try:
        fig.write_image(FIG / "mae_leaderboard.png")
    except Exception as e:
        print("png skipped:", e)
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
    if "companion_pr_auc" in ok.columns:
        fig2 = go.Figure(go.Bar(x=ok["model"], y=ok["companion_pr_auc"], name="companion PR-AUC"))
        fig2.update_layout(title="Companion P(slip ≥ 12m) PR-AUC")
        fig2.write_html(FIG / "companion_pr.html")
        try:
            fig2.show()
        except Exception as e:
            print("show skipped:", e)
'''

CURVES = r'''
display(Markdown("## Learning curves"))
for model in ["catboost", "xgboost", "lightgbm", "seq_cnn", "nasnet_cnn", "ft_transformer", "tabm"]:
    p = RESULTS / model / "history.csv"
    if not p.exists():
        continue
    h = pd.read_csv(p)
    if h.empty:
        continue
    fig = go.Figure()
    for col in ("train_loss", "val_loss", "val_mae", "train_mae"):
        if col in h.columns:
            fig.add_trace(go.Scatter(x=h.get("step"), y=h[col], mode="lines", name=col))
    fig.update_layout(title=f"{model} history")
    fig.write_html(FIG / f"history_{model}.html")
    try:
        fig.show()
    except Exception as e:
        print("show skipped:", e)
'''

FOOT = r'''
display(Markdown("## What this is not"))
display(Markdown(
    "- Not a DPP restudy. Not another queue. Not a second Resource Adequacy test.\\n"
    "- FERC-730 was **not** a clean bulk table; transmission delay is a NERC/MTEP callout "
    "(110 of 1,160 NERC LTRA projects delayed), not a Platinum model.\\n"
    "- NASNet-as-image is included to **actually train** (100+20), not because it should win."
))
display(Markdown("Study the ramp once. Revalidate only what changes."))
'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb["cells"] = [
        md("# Platinum performance (val only)"),
        code(SETUP.strip()),
        md("## GIA delay distribution"),
        code(GIA.strip()),
        md("## Leaderboard"),
        code(LB.strip()),
        code(CURVES.strip()),
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
