"""PIT peripherals: delayed-MW pile + gold flags. Never joins future labels."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR
from src.gold.cod_delay import is_gia_row
from src.modeling.platinum2.eval_protocol import HORIZON_STEPS, PRIMARY_TARGET, load_series  # re-exported for cards

DELAY_PANEL = GOLD_DIR / "delay" / "cod_delay_panel.parquet"
ENRICHED_PANEL = GOLD_DIR / "withdrawal_panel_enriched.parquet"


def _holt_or_naive(history: np.ndarray, horizon_steps: int) -> tuple[float, str]:
    y = np.asarray(history, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) == 0:
        return float("nan"), "missing"
    if len(y) < 4:
        return float(y[-1]), "naive"
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        fit = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal=None).fit(optimized=True)
        fc = np.asarray(fit.forecast(horizon_steps), dtype=float)
        return float(fc[-1]), "holt_damped"
    except Exception:
        return float(y[-1]), "naive"


def pile_asof(as_of, series: pd.DataFrame | None = None) -> dict[str, Any]:
    """Last EIA delayed-MW snapshot with available_date ≤ as_of, plus Holt 3m/12m."""
    ser = load_series() if series is None else series
    as_of = pd.Timestamp(as_of)
    hist = ser[ser["available_date"] <= as_of]
    empty = {
        "delayed_mw_now": None,
        "gia_delayed_mw_now": None,
        "delayed_mw_h3": None,
        "delayed_mw_h12": None,
        "pile_percentile_pit": None,
        "pile_asof": None,
        "pile_forecast_engine": None,
        "n_history": 0,
        "note": "No EIA delayed-MW snapshot with available_date ≤ observation_date (series starts 2022-03).",
    }
    if hist.empty:
        return empty
    last = hist.iloc[-1]
    y = pd.to_numeric(hist[PRIMARY_TARGET], errors="coerce").to_numpy(dtype=float)
    now = float(y[-1]) if np.isfinite(y[-1]) else float("nan")
    finite = y[np.isfinite(y)]
    pct = float((finite <= now).mean()) if np.isfinite(now) and len(finite) else float("nan")
    h3, eng3 = _holt_or_naive(y, HORIZON_STEPS[3])
    h12, eng12 = _holt_or_naive(y, HORIZON_STEPS[12])
    engine = eng12 if eng12 == eng3 else f"{eng3}/h3;{eng12}/h12"
    gia_now = pd.to_numeric(last.get("gia_delayed_mw"), errors="coerce")
    return {
        "delayed_mw_now": None if not np.isfinite(now) else now,
        "gia_delayed_mw_now": None if pd.isna(gia_now) else float(gia_now),
        "delayed_mw_h3": None if not np.isfinite(h3) else h3,
        "delayed_mw_h12": None if not np.isfinite(h12) else h12,
        "pile_percentile_pit": None if not np.isfinite(pct) else pct,
        "pile_asof": str(pd.Timestamp(last["available_date"]).date()),
        "pile_forecast_engine": engine,
        "n_history": int(len(hist)),
        "note": (
            "EIA planned delayed MW (delay ≥12m vs first seen). "
            "GIA overlay is a thin fuzzy match — do not treat as the full GIA pile. "
            "3m/12m are Holt (or naive) from history ≤ as-of; not 2024 actuals."
        ),
    }


def _gia_series(panel: pd.DataFrame) -> pd.Series:
    if "is_gia" in panel.columns:
        return panel["is_gia"].fillna(False).astype(bool)
    sp = panel["study_phase"] if "study_phase" in panel.columns else pd.Series(pd.NA, index=panel.index)
    pg = panel["post_gia_status"] if "post_gia_status" in panel.columns else pd.Series(pd.NA, index=panel.index)
    return pd.Series([is_gia_row(a, b) for a, b in zip(sp, pg, strict=False)], index=panel.index)


def join_project_facts(meta: pd.DataFrame) -> pd.DataFrame:
    """Capacity, GIA, energy-community, POI — current state only (no slip/withdraw labels)."""
    keys = meta[["project_key", "observation_date"]].copy()
    keys["observation_date"] = pd.to_datetime(keys["observation_date"])
    out = keys.copy()

    if DELAY_PANEL.exists():
        import pyarrow.parquet as pq

        have = set(pq.read_schema(DELAY_PANEL).names)
        delay_cols = [
            c
            for c in (
                "project_key",
                "observation_date",
                "is_gia",
                "study_phase",
                "post_gia_status",
                "transmission_owner",
                "poi_name",
            )
            if c in have
        ]
        delay = pd.read_parquet(DELAY_PANEL, columns=delay_cols)
        delay["observation_date"] = pd.to_datetime(delay["observation_date"])
        delay["is_gia"] = _gia_series(delay)
        keep = [
            c
            for c in ("project_key", "observation_date", "is_gia", "transmission_owner", "poi_name")
            if c in delay.columns
        ]
        out = out.merge(delay[keep].drop_duplicates(["project_key", "observation_date"]), on=["project_key", "observation_date"], how="left")

    if ENRICHED_PANEL.exists():
        enr = pd.read_parquet(ENRICHED_PANEL)
        want = [
            "project_key",
            "observation_date",
            "capacity_mw",
            "energy_community_eligible",
            "poi_name",
        ]
        use = [c for c in want if c in enr.columns]
        enr = enr[use].copy()
        enr["observation_date"] = pd.to_datetime(enr["observation_date"])
        merged = out.merge(enr, on=["project_key", "observation_date"], how="left", suffixes=("", "_enr"))
        for c in ("capacity_mw", "energy_community_eligible", "poi_name"):
            src = f"{c}_enr"
            if src in merged.columns:
                if c not in merged.columns:
                    merged[c] = merged[src]
                else:
                    merged[c] = merged[c].where(merged[c].notna(), merged[src])
                merged = merged.drop(columns=[src], errors="ignore")
        out = merged

    if "is_gia" not in out.columns:
        out["is_gia"] = pd.NA
    return out
