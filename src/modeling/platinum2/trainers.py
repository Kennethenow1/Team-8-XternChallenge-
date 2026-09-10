"""Thin delayed-MW forecasters. Each returns the eval_protocol bundle."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.modeling.platinum2.eval_protocol import (
    PRIMARY_TARGET,
    load_series,
    ma3_pred,
    naive_pred,
    run_backtest,
    seasonal_naive_pred,
)


def fit_seasonal_naive(*, model_name: str = "seasonal_naive") -> dict[str, Any]:
    return run_backtest(
        model_name=model_name,
        forecast_fn=lambda hist, h: seasonal_naive_pred(hist[PRIMARY_TARGET].to_numpy(), h),
    )


def fit_naive(*, model_name: str = "naive") -> dict[str, Any]:
    return run_backtest(
        model_name=model_name,
        forecast_fn=lambda hist, h: naive_pred(hist[PRIMARY_TARGET].to_numpy(), h),
    )


def fit_ma3(*, model_name: str = "ma3") -> dict[str, Any]:
    return run_backtest(
        model_name=model_name,
        forecast_fn=lambda hist, h: ma3_pred(hist[PRIMARY_TARGET].to_numpy(), h),
    )


def fit_holt(*, model_name: str = "holt") -> dict[str, Any]:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"statsmodels unavailable: {e}"}

    def _fn(hist: pd.DataFrame, horizon_steps: int) -> float:
        y = pd.to_numeric(hist[PRIMARY_TARGET], errors="coerce").to_numpy(dtype=float)
        y = y[np.isfinite(y)]
        if len(y) < 4:
            return naive_pred(y, horizon_steps)
        try:
            fit = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal=None).fit(optimized=True)
            fc = np.asarray(fit.forecast(horizon_steps), dtype=float)
            return float(fc[-1])
        except Exception:
            return naive_pred(y, horizon_steps)

    m = run_backtest(model_name=model_name, forecast_fn=_fn)
    m["_model"] = "holt_damped"
    return m


def fit_arima(*, model_name: str = "arima") -> dict[str, Any]:
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"statsmodels unavailable: {e}"}

    def _fn(hist: pd.DataFrame, horizon_steps: int) -> float:
        y = pd.to_numeric(hist[PRIMARY_TARGET], errors="coerce").to_numpy(dtype=float)
        y = y[np.isfinite(y)]
        if len(y) < 8:
            return float("nan")
        try:
            fit = ARIMA(y, order=(1, 0, 1)).fit()
            fc = np.asarray(fit.forecast(steps=horizon_steps), dtype=float)
            return float(fc[-1])
        except Exception:
            return float("nan")

    m = run_backtest(model_name=model_name, forecast_fn=_fn)
    if m.get("status") == "ok" and not np.isfinite(m.get("rmse", float("nan"))):
        m["status"] = "skipped"
        m["reason"] = "ARIMA did not identify / all-NaN forecasts"
    return m


def fit_ridge_lags(*, model_name: str = "ridge_lags") -> dict[str, Any]:
    from sklearn.linear_model import Ridge

    series = load_series()

    def _fn(hist: pd.DataFrame, horizon_steps: int) -> float:
        y_h = pd.to_numeric(hist[PRIMARY_TARGET], errors="coerce").to_numpy(dtype=float)
        sh = pd.to_numeric(hist.get("shift_in_mw"), errors="coerce").fillna(0.0).to_numpy(dtype=float)
        n = len(y_h)
        X, yy = [], []
        for i in range(n):
            j = i + horizon_steps
            if j >= n:
                break
            lag1 = y_h[i]
            lag2 = y_h[i - 1] if i >= 1 else y_h[i]
            lag4 = y_h[i - 3] if i >= 3 else y_h[i]
            X.append([lag1, lag2, lag4, sh[i]])
            yy.append(y_h[j])
        if len(X) < 3:
            return naive_pred(y_h, horizon_steps)
        model = Ridge(alpha=1.0)
        model.fit(np.asarray(X, dtype=float), np.asarray(yy, dtype=float))
        feat = np.array(
            [
                y_h[-1],
                y_h[-2] if n >= 2 else y_h[-1],
                y_h[-4] if n >= 4 else y_h[-1],
                sh[-1],
            ],
            dtype=float,
        )
        return float(model.predict(feat.reshape(1, -1))[0])

    m = run_backtest(model_name=model_name, forecast_fn=_fn, series=series)
    m["_model"] = "ridge_lags"
    return m


def fit_timesfm(*, model_name: str = "timesfm") -> dict[str, Any]:
    from src.modeling.train_timesfm import timesfm_forecast

    def _fn(hist: pd.DataFrame, horizon_steps: int) -> float:
        y = pd.to_numeric(hist[PRIMARY_TARGET], errors="coerce").to_numpy(dtype=float)
        pred, err = timesfm_forecast(y, horizon_steps)
        if err and not np.isfinite(pred).any():
            return naive_pred(y, horizon_steps)
        return float(pred[horizon_steps - 1] if len(pred) >= horizon_steps else pred[-1])

    return run_backtest(model_name=model_name, forecast_fn=_fn)
