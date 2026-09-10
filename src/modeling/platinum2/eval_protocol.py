"""Rolling-origin delayed-MW eval. Val only for selection; 2024 sealed."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

SERIES_PATH = GOLD_DIR / "delay" / "platinum2" / "gia_delayed_mw_monthly.parquet"
MIN_12M_VAL_FOLDS = 4
HORIZON_STEPS = {3: 1, 12: 4}
SEASONAL_PERIOD = 4
PRIMARY_TARGET = "delayed_mw"


def load_series() -> pd.DataFrame:
    if not SERIES_PATH.exists():
        raise FileNotFoundError(f"missing {SERIES_PATH}; run scripts/run_platinum2_gold.py")
    df = pd.read_parquet(SERIES_PATH)
    df["available_date"] = pd.to_datetime(df["available_date"])
    return df.sort_values("available_date").reset_index(drop=True)


def _ym(ts) -> str:
    t = pd.Timestamp(ts)
    return f"{t.year:04d}-{t.month:02d}"


def fold_split(target_year: int) -> str:
    if target_year >= 2025:
        return "score"
    if target_year == 2024:
        return "test"
    if target_year <= 2023:
        return "val"
    return "other"


def seasonal_naive_pred(history: np.ndarray, horizon_steps: int) -> float:
    s = np.asarray(history, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    # ŷ_{T+h} = y_{T+h-4k}; k=ceil(h/4). For h=4 → y_T; for h=1 → y_{T-3}.
    k = int(np.ceil(horizon_steps / SEASONAL_PERIOD))
    idx = len(s) - 1 + horizon_steps - SEASONAL_PERIOD * k
    if 0 <= idx < len(s):
        return float(s[idx])
    return float(s[-1])


def naive_pred(history: np.ndarray, horizon_steps: int) -> float:
    s = np.asarray(history, dtype=float)
    s = s[np.isfinite(s)]
    return float(s[-1]) if len(s) else float("nan")


def ma3_pred(history: np.ndarray, horizon_steps: int) -> float:
    s = np.asarray(history, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return float("nan")
    w = s[-3:] if len(s) >= 3 else s
    return float(np.nanmean(w))


ForecastFn = Callable[[pd.DataFrame, int], float]


def iterate_folds(
    series: pd.DataFrame,
    *,
    horizon_months: int,
    split: str = SELECTION_SPLIT,
    target_col: str = PRIMARY_TARGET,
) -> list[dict[str, Any]]:
    steps = HORIZON_STEPS[int(horizon_months)]
    y = pd.to_numeric(series[target_col], errors="coerce").to_numpy(dtype=float)
    dates = pd.to_datetime(series["available_date"])
    folds: list[dict[str, Any]] = []
    for i in range(len(series)):
        j = i + steps
        if j >= len(series):
            continue
        origin_year = int(dates.iloc[i].year)
        target_year = int(dates.iloc[j].year)
        role = fold_split(target_year)
        if split == "val":
            if horizon_months == 12 and target_year > 2023:
                continue
            if horizon_months == 3 and not (origin_year == 2023 and target_year <= 2023):
                continue
            if role != "val":
                continue
        elif role != split:
            continue
        hist = series.iloc[: i + 1].copy()
        folds.append(
            {
                "origin_idx": int(i),
                "target_idx": int(j),
                "origin_ym": _ym(dates.iloc[i]),
                "target_ym": _ym(dates.iloc[j]),
                "origin_year": origin_year,
                "target_year": target_year,
                "split": role,
                "actual": float(y[j]),
                "history": hist,
            }
        )
    return folds


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(pred, dtype=float)
    m = np.isfinite(a) & np.isfinite(p)
    if not m.any():
        return {"n": 0.0, "rmse": float("nan"), "mae": float("nan"), "mape": float("nan")}
    err = p[m] - a[m]
    mape = float(np.nanmean(np.abs(err) / np.clip(np.abs(a[m]), 1.0, None)))
    return {
        "n": float(m.sum()),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae": float(np.mean(np.abs(err))),
        "mape": mape,
    }


def run_backtest(
    *,
    model_name: str,
    forecast_fn: ForecastFn,
    series: pd.DataFrame | None = None,
    target_col: str = PRIMARY_TARGET,
    split: str = SELECTION_SPLIT,
) -> dict[str, Any]:
    assert_selection_split(split)
    series = series if series is not None else load_series()
    if len(series) < 12:
        return {
            "model": model_name,
            "status": "skipped",
            "reason": f"need ≥12 snapshots, got {len(series)}; refuse stub TimesFM-style run",
        }

    by_h: dict[str, Any] = {}
    hist_rows: list[dict[str, float]] = []
    all_folds: list[dict[str, Any]] = []
    for h in (3, 12):
        folds = iterate_folds(series, horizon_months=h, split=split, target_col=target_col)
        actual, pred, snaive = [], [], []
        for f in folds:
            yhat = forecast_fn(f["history"], HORIZON_STEPS[h])
            sn = seasonal_naive_pred(f["history"][target_col].to_numpy(), HORIZON_STEPS[h])
            actual.append(f["actual"])
            pred.append(float(yhat) if yhat is not None else float("nan"))
            snaive.append(sn)
            row = {
                "horizon_months": h,
                "origin_ym": f["origin_ym"],
                "target_ym": f["target_ym"],
                "actual": f["actual"],
                "pred": float(yhat) if yhat is not None else float("nan"),
                "seasonal_naive": sn,
            }
            all_folds.append(row)
            hist_rows.append(
                {
                    "step": float(len(hist_rows)),
                    "train_loss": abs(sn - f["actual"]) if np.isfinite(sn) else float("nan"),
                    "val_loss": abs(float(yhat) - f["actual"]) if np.isfinite(yhat) else float("nan"),
                    "horizon_months": float(h),
                }
            )
        m = _metrics(np.asarray(actual), np.asarray(pred))
        b = _metrics(np.asarray(actual), np.asarray(snaive))
        m["seasonal_naive_rmse"] = b["rmse"]
        m["beats_seasonal_naive"] = bool(
            np.isfinite(m["rmse"]) and np.isfinite(b["rmse"]) and m["rmse"] + 1e-9 < b["rmse"]
        )
        m["n_folds"] = int(len(folds))
        by_h[str(h)] = m

    n12 = int(by_h["12"].get("n_folds") or 0)
    status = "ok"
    reason = None
    if n12 < MIN_12M_VAL_FOLDS:
        status = "skipped"
        reason = f"only {n12} 12-month val folds (need {MIN_12M_VAL_FOLDS}); 2024 is sealed so 2023→2024 is test"
        # still keep 3m numbers
        if int(by_h["3"].get("n_folds") or 0) >= 1:
            status = "ok"
            reason = (
                f"12m val folds={n12} (<{MIN_12M_VAL_FOLDS}); selection uses 3-month-ahead. "
                "12m 2023→2024 remains sealed test."
            )

    return {
        "model": model_name,
        "status": status,
        "reason": reason,
        "split": split,
        "target": target_col,
        "rmse": by_h["12"]["rmse"],
        "mae": by_h["12"]["mae"],
        "mape": by_h["12"]["mape"],
        "rmse_h3": by_h["3"]["rmse"],
        "mape_h3": by_h["3"]["mape"],
        "n_folds_h12": n12,
        "n_folds_h3": int(by_h["3"].get("n_folds") or 0),
        "beats_seasonal_naive": by_h["12"]["beats_seasonal_naive"] if n12 else by_h["3"]["beats_seasonal_naive"],
        "horizons": by_h,
        "folds": all_folds,
        "history": hist_rows,
        "n_snapshots": int(len(series)),
    }
