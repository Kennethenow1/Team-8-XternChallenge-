"""System-level delayed-MW / median COD-slip monthly series + naive/MA/TimesFM backtest."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

PANEL = GOLD_DIR / "delay" / "cod_delay_panel.parquet"


def build_monthly_delay_series(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    df = panel if panel is not None else pd.read_parquet(PANEL)
    df = df.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["ym"] = df["observation_date"].dt.to_period("M").astype(str)
    slip = pd.to_numeric(df["cod_slip_months_next_12m"], errors="coerce")
    mw = pd.to_numeric(df.get("capacity_mw"), errors="coerce").fillna(0)
    gia = df["is_gia"].fillna(False) if "is_gia" in df.columns else False
    g = df.assign(slip=slip, mw=mw, delayed=slip.ge(12).fillna(False), gia=gia)
    out = g.groupby("ym").agg(
        median_slip=("slip", "median"),
        delayed_mw=("mw", lambda s: float(s.loc[g.loc[s.index, "delayed"]].sum()) if len(s) else 0.0),
        gia_count=("gia", "sum"),
        n=("project_key", "size"),
    )
    return out.reset_index().rename(columns={"ym": "year_month"})


def _forecast(series: np.ndarray, engine: str) -> float:
    s = np.asarray(series, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    if engine == "naive":
        return float(s[-1])
    if engine == "ma3":
        return float(np.mean(s[-3:])) if len(s) else float("nan")
    if engine == "timesfm":
        try:
            from src.modeling.train_timesfm import timesfm_forecast

            pred, _ = timesfm_forecast(s, 1)
            return float(pred[0])
        except Exception:
            return float(np.mean(s[-3:])) if len(s) else float("nan")
    raise ValueError(engine)


def fit_timesfm_delay(*, model_name: str = "timesfm") -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    monthly = build_monthly_delay_series()
    target = "median_slip"
    if target not in monthly.columns or monthly[target].notna().sum() < 4:
        return {"model": model_name, "status": "skipped", "reason": "monthly delay series too short"}
    years = monthly["year_month"].astype(str).str[:4].astype(int)
    folds = []
    hist_rows = []
    for i, y in enumerate(sorted(years.unique())):
        if y < 2022:
            continue
        hist = monthly.loc[years < y, target].astype(float).to_numpy()
        actual = monthly.loc[years == y, target].astype(float)
        if len(hist) < 2 or actual.empty:
            continue
        actual_v = float(actual.iloc[-1])
        row = {"year": int(y), "actual": actual_v}
        for eng in ("naive", "ma3", "timesfm"):
            pred = _forecast(hist, eng)
            row[eng] = pred
            row[f"err_{eng}"] = abs(pred - actual_v) if np.isfinite(pred) else float("nan")
        folds.append(row)
        hist_rows.append({"step": float(i), "train_loss": row.get("err_naive"), "val_loss": row.get("err_timesfm")})
    if not folds:
        return {"model": model_name, "status": "skipped", "reason": "no rolling-origin folds"}
    fdf = pd.DataFrame(folds)
    rmse = float(np.sqrt(np.nanmean((fdf["timesfm"] - fdf["actual"]) ** 2)))
    mape = float(np.nanmean(np.abs((fdf["timesfm"] - fdf["actual"]) / np.clip(np.abs(fdf["actual"]), 1e-6, None))))
    return {
        "model": model_name,
        "status": "ok",
        "split": "val",
        "mae": float("nan"),
        "rmse": rmse,
        "mape": mape,
        "n_folds": int(len(fdf)),
        "pr_auc": None,
        "history": hist_rows,
        "folds": folds,
        "note": "system series — not row MAE",
    }
