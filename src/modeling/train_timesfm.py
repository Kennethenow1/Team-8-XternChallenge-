"""TimesFM-3 system monthly forecasting branch (rolling-origin backtests)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.eval_protocol import assert_selection_split, load_split_manifest
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs

PANEL_PATH = GOLD_DIR / "withdrawal_panel_enriched.parquet"
METRICS_PATH = ARTIFACTS_DIR / "metrics" / "timesfm_system_forecast.md"

_TFM3_MODEL: Any | None = None
_TFM3_LOAD_ERROR: str | None = None


def build_monthly_system_series() -> pd.DataFrame:
    """Monthly system aggregates: withdrawal MW, counts, macros where available."""
    if not PANEL_PATH.exists():
        raise FileNotFoundError(PANEL_PATH)
    panel = pd.read_parquet(PANEL_PATH)
    panel["observation_date"] = pd.to_datetime(panel["observation_date"])
    panel["year_month"] = panel["observation_date"].dt.to_period("M")

    macro_cols = [
        c
        for c in (
            "miso_mean_demand_mw",
            "miso_peak_demand_mw",
            "interest_rate_at_observation",
            "construction_cost_index_change_12m",
        )
        if c in panel.columns
    ]

    monthly = panel.groupby("year_month", as_index=False).agg(
        withdrawal_count=("withdraw_next_12m", "sum"),
        project_count=("project_key", "count"),
        total_capacity_mw=("capacity_mw", "sum"),
        **{c: (c, "mean") for c in macro_cols},
    )
    monthly["year_month"] = monthly["year_month"].astype(str)
    monthly = monthly.sort_values("year_month").reset_index(drop=True)
    return monthly


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred) & (y_true != 0)
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if not mask.any():
        return float("nan")
    return float(np.sqrt(np.mean((y_true[mask] - y_pred[mask]) ** 2)))


def naive_forecast(series: np.ndarray, horizon: int = 1) -> np.ndarray:
    return np.full(horizon, series[-1] if len(series) else np.nan)


def ma_forecast(series: np.ndarray, window: int = 3, horizon: int = 1) -> np.ndarray:
    w = series[-window:] if len(series) >= window else series
    return np.full(horizon, float(np.nanmean(w)))


def arima_forecast(series: np.ndarray, horizon: int = 1) -> tuple[np.ndarray, str | None]:
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError as e:
        return np.full(horizon, np.nan), f"statsmodels unavailable: {e}"
    if len(series) < 8:
        return np.full(horizon, np.nan), "series too short for ARIMA"
    try:
        fit = ARIMA(series, order=(1, 0, 1)).fit()
        fc = fit.forecast(steps=horizon)
        return np.asarray(fc, dtype=float), None
    except Exception as e:  # noqa: BLE001
        return np.full(horizon, np.nan), str(e)


def _get_timesfm3() -> tuple[Any | None, str | None]:
    """Lazy-load TimesFM-3 forecaster (CUDA if available)."""
    global _TFM3_MODEL, _TFM3_LOAD_ERROR
    if _TFM3_MODEL is not None:
        return _TFM3_MODEL, None
    if _TFM3_LOAD_ERROR is not None:
        return None, _TFM3_LOAD_ERROR
    try:
        import torch
        import timesfm
    except ImportError as e:
        _TFM3_LOAD_ERROR = f"timesfm not installed: {e}"
        return None, _TFM3_LOAD_ERROR
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        print(f"[timesfm] loading TimesFM-3 on {device} ...", flush=True)
        model = timesfm.TimesFM3Forecaster.from_pretrained(
            "google/timesfm-3.0-pytorch",
            device=device,
        )
        _TFM3_MODEL = model
        print("[timesfm] TimesFM-3 ready", flush=True)
        return model, None
    except Exception as e:  # noqa: BLE001
        # Fallback: TimesFM 2.5 if 3.0 checkpoint unavailable
        try:
            print(f"[timesfm] TimesFM-3 load failed ({e}); trying 2.5 ...", flush=True)
            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                "google/timesfm-2.5-200m-pytorch"
            )
            model.compile(
                timesfm.ForecastConfig(
                    max_context=512,
                    max_horizon=64,
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                    force_flip_invariance=True,
                    infer_is_positive=True,
                    fix_quantile_crossing=True,
                    per_core_batch_size=1,
                )
            )
            _TFM3_MODEL = ("2p5", model)
            return _TFM3_MODEL, None
        except Exception as e2:  # noqa: BLE001
            _TFM3_LOAD_ERROR = f"TimesFM-3 failed: {e}; 2.5 failed: {e2}"
            return None, _TFM3_LOAD_ERROR


def timesfm_forecast(series: np.ndarray, horizon: int = 1) -> tuple[np.ndarray, str | None]:
    """Zero-shot forecast with TimesFM-3 (or 2.5 fallback)."""
    series = np.asarray(series, dtype=float)
    series = series[np.isfinite(series)]
    if len(series) < 3:
        return np.full(horizon, np.nan), "series too short for TimesFM"

    model, err = _get_timesfm3()
    if model is None:
        return np.full(horizon, np.nan), err or "TimesFM unavailable"

    try:
        if isinstance(model, tuple) and model[0] == "2p5":
            point, _q = model[1].forecast(horizon=horizon, inputs=[series])
            pred = np.asarray(point[0], dtype=float)
            return pred, "backend=timesfm-2.5"
        # TimesFM3Forecaster.predict → ForecastOutput(forecast, quantiles, ts_id)
        out = model.predict(
            context=series,
            horizon=horizon,
            make_positive=True,
            use_znorm=True,
        )
        if hasattr(out, "forecast") and out.forecast is not None:
            pred = np.asarray(out.forecast, dtype=float).reshape(-1)
        elif hasattr(out, "point_forecast"):
            pred = np.asarray(out.point_forecast, dtype=float).reshape(-1)
        elif isinstance(out, (tuple, list)):
            pred = np.asarray(out[0], dtype=float).reshape(-1)
        else:
            pred = np.asarray(out, dtype=float).reshape(-1)
        if pred.size < horizon:
            pred = np.pad(pred, (0, horizon - pred.size), constant_values=np.nan)
        return pred[:horizon], "backend=timesfm-3.0"
    except Exception as e:  # noqa: BLE001
        return np.full(horizon, np.nan), f"TimesFM forecast failed: {e}"


def rolling_origin_backtest(
    monthly: pd.DataFrame,
    target_col: str = "withdrawal_count",
    *,
    min_train: int | None = None,
    horizon: int = 1,
    val_year: int = 2023,
) -> dict[str, Any]:
    """Rolling-origin folds with live print per fold."""
    y = monthly[target_col].astype(float).to_numpy()
    months = monthly["year_month"].astype(str).tolist()
    if min_train is None:
        min_train = max(2, len(y) // 3)
    folds: list[dict[str, Any]] = []

    val_idx = [i for i, m in enumerate(months) if m.startswith(str(val_year))]
    # Annual panel grain often yields one val fold; also roll over earlier years for system RMSE/MAPE
    # (system branch is not used for project-row model selection).
    all_eval = [i for i in range(min_train, len(y)) if i + horizon <= len(y)]
    eval_idx = sorted(set(val_idx) | set(all_eval))
    if not eval_idx:
        eval_idx = list(range(max(min_train, len(y) - 6), len(y)))

    for i in eval_idx:
        if i < min_train:
            continue
        train_y = y[:i]
        actual = y[i : i + horizon]
        if len(actual) < horizon:
            continue

        preds = {
            "naive": naive_forecast(train_y, horizon)[0],
            "ma3": ma_forecast(train_y, 3, horizon)[0],
        }
        arima_p, arima_note = arima_forecast(train_y, horizon)
        preds["arima"] = float(arima_p[0])
        tfm_p, tfm_note = timesfm_forecast(train_y, horizon)
        preds["timesfm"] = float(tfm_p[0])

        fold = {
            "fold_end_month": months[i - 1] if i > 0 else None,
            "target_month": months[i],
            "is_val_year": months[i].startswith(str(val_year)),
            "actual": float(actual[0]),
            "preds": preds,
            "arima_note": arima_note,
            "timesfm_note": tfm_note,
        }
        folds.append(fold)
        print(
            f"[timesfm] fold target={fold['target_month']} actual={fold['actual']:.2f} "
            f"naive={preds['naive']:.2f} ma3={preds['ma3']:.2f} arima={preds['arima']:.2f} "
            f"timesfm={preds['timesfm']:.2f} note={tfm_note}",
            flush=True,
        )

    summary: dict[str, Any] = {"target": target_col, "n_folds": len(folds), "models": {}}
    for name in ("naive", "ma3", "arima", "timesfm"):
        actuals = np.array([f["actual"] for f in folds], dtype=float)
        preds_a = np.array([f["preds"][name] for f in folds], dtype=float)
        summary["models"][name] = {"rmse": _rmse(actuals, preds_a), "mape": _mape(actuals, preds_a)}
    summary["folds"] = folds
    return summary


def run_timesfm_experiment(*, save: bool = True) -> dict[str, Any]:
    assert_selection_split("val")
    ensure_artifact_dirs()
    manifest = load_split_manifest()
    val_year = int(manifest.get("validation_year", 2023))
    monthly = build_monthly_system_series()
    result = rolling_origin_backtest(monthly, val_year=val_year)

    if save:
        lines = [
            "# TimesFM system monthly forecast (rolling-origin)",
            "",
            "**System-level branch** (TimesFM-3). Feeds future system conditions; "
            "not used alone for project-row model selection.",
            f"Target: `{result.get('target')}` | folds: {result.get('n_folds')}",
            "",
            "| model | RMSE | MAPE |",
            "|-------|------|------|",
        ]
        for name, m in (result.get("models") or {}).items():
            lines.append(f"| {name} | {m.get('rmse')} | {m.get('mape')} |")
        tfm_notes = [f.get("timesfm_note") for f in result.get("folds", []) if f.get("timesfm_note")]
        tfm_ok = next((n for n in tfm_notes if n and str(n).startswith("backend=")), None)
        tfm_note = tfm_ok or (tfm_notes[0] if tfm_notes else None)
        if tfm_note:
            lines.extend(["", f"**TimesFM:** {tfm_note}"])
        n_val = sum(1 for f in result.get("folds", []) if f.get("is_val_year"))
        lines.extend(["", f"Val-year folds: {n_val} / {result.get('n_folds')} (panel grain is annual Dec snapshots).", ""])
        METRICS_PATH.write_text("\n".join(lines), encoding="utf-8")
        (ARTIFACTS_DIR / "metrics" / "timesfm_system_forecast.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
    return result
