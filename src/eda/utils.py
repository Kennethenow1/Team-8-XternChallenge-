"""Read-only EDA helpers. Does not write under data/gold."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go

from src.common.paths import REPO_ROOT

REPORTS_EDA_DIR = REPO_ROOT / "reports" / "eda"
FIG_DIR = REPORTS_EDA_DIR / "figures"
MIN_RATE_N = 30

# Features that are heavily right-skewed; plot with log1p only (never mutate source).
LOG1P_PLOT_COLS = (
    "capacity_mw",
    "network_upgrade_cost",
    "upgrade_cost_per_mw",
    "storm_property_damage_12m",
    "mtep_investment_nearby_usd",
    "other_active_mw_same_state",
    "other_active_mw_same_poi",
    "other_active_mw_same_technology",
    "prior_12m_withdrawn_mw",
    "developer_total_active_mw",
    "nearby_queue_mw",
)


def ensure_eda_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_EDA_DIR.mkdir(parents=True, exist_ok=True)


def save_mpl(fig: plt.Figure, stem: str, dpi: int = 140) -> Path:
    ensure_eda_dirs()
    path = FIG_DIR / f"{stem}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def save_plotly(fig: go.Figure, stem: str, *, write_png: bool = True) -> dict[str, Path]:
    ensure_eda_dirs()
    out: dict[str, Path] = {}
    html_path = FIG_DIR / f"{stem}.html"
    fig.write_html(html_path, include_plotlyjs="cdn", full_html=True)
    out["html"] = html_path
    if write_png:
        png_path = FIG_DIR / f"{stem}.png"
        try:
            fig.write_image(png_path, scale=2)
            out["png"] = png_path
        except Exception:
            # Kaleido optional; HTML is always saved.
            pass
    return out


def rate_table(
    df: pd.DataFrame,
    group_col: str,
    event_col: str,
    *,
    min_n: int = MIN_RATE_N,
) -> pd.DataFrame:
    """Group rates with n shown; suppress rate when n < min_n."""
    g = (
        df.groupby(group_col, dropna=False)
        .agg(n=(event_col, "size"), events=(event_col, "sum"))
        .reset_index()
    )
    g["rate"] = g["events"] / g["n"]
    g["rate_plot"] = g["rate"].where(g["n"] >= min_n)
    g["suppressed"] = g["n"] < min_n
    g["label"] = g.apply(
        lambda r: f"{r[group_col]} (n={int(r['n'])})",
        axis=1,
    )
    return g.sort_values("n", ascending=False)


def year_of(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.year


def log1p_plot_series(s: pd.Series) -> pd.Series:
    """Return log1p for plotting only; does not modify stored columns."""
    import numpy as np

    x = pd.to_numeric(s, errors="coerce")
    return np.log1p(x.clip(lower=0))
