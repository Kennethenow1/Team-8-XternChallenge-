#!/usr/bin/env python3
"""Train Platinum 2 delayed-MW models (val only; 2024 sealed)."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RESULTS_ROOT = REPO / "platinum2" / "results"


def _public(m: dict) -> dict:
    skip = {"history", "folds", "traceback"}
    out = {}
    for k, v in (m or {}).items():
        if str(k).startswith("_") or k in skip:
            continue
        if isinstance(v, np.ndarray):
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v)
        elif isinstance(v, (float, int, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict) and k in {"horizons"}:
            try:
                json.dumps(v, default=str)
                out[k] = v
            except TypeError:
                out[k] = {kk: str(vv) for kk, vv in v.items()}
    return out


def _write_plots(dest: Path, m: dict, hist: pd.DataFrame) -> None:
    try:
        import plotly.graph_objects as go
    except Exception as e:  # noqa: BLE001
        print(f"  plotly skipped: {e}", flush=True)
        return
    (dest / "plots").mkdir(parents=True, exist_ok=True)
    folds = m.get("folds") or []
    if folds:
        fdf = pd.DataFrame(folds)
        fig = go.Figure()
        if "target_ym" in fdf.columns:
            fig.add_trace(go.Scatter(x=fdf["target_ym"], y=fdf["actual"], mode="lines+markers", name="actual"))
            fig.add_trace(go.Scatter(x=fdf["target_ym"], y=fdf["pred"], mode="lines+markers", name="pred"))
        fig.update_layout(title=f"{m.get('model')} delayed MW", yaxis_title="MW")
        fig.write_html(dest / "plots" / "val_pred_vs_actual.html")
    if not hist.empty:
        fig = go.Figure()
        for col, name in (("train_loss", "seasonal-naive abs err"), ("val_loss", "model abs err")):
            if col in hist.columns:
                fig.add_trace(go.Scatter(x=hist.get("step"), y=hist[col], mode="lines", name=name))
        fig.update_layout(title="Abs error by fold", xaxis_title="fold")
        fig.write_html(dest / "plots" / "history.html")


def save_bundle(model_id: str, m: dict) -> None:
    dest = RESULTS_ROOT / model_id
    (dest / "models").mkdir(parents=True, exist_ok=True)
    (dest / "plots").mkdir(parents=True, exist_ok=True)
    pub = _public(m or {})
    pub.setdefault("model", model_id)
    pub.setdefault("status", (m or {}).get("status", "skipped"))
    (dest / "metrics.json").write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")
    hist = pd.DataFrame(m.get("history") or [])
    hist.to_csv(dest / "history.csv", index=False)
    _write_plots(dest, m or {}, hist)
    if m.get("folds"):
        pd.DataFrame(m["folds"]).to_parquet(dest / "val_predictions.parquet", index=False)
    lb_path = RESULTS_ROOT / "leaderboard.csv"
    row = {
        "model": model_id,
        "split": "val",
        "status": pub.get("status"),
        "rmse_h12": pub.get("rmse"),
        "mape_h12": pub.get("mape"),
        "rmse_h3": pub.get("rmse_h3"),
        "mape_h3": pub.get("mape_h3"),
        "n_folds_h12": pub.get("n_folds_h12"),
        "n_folds_h3": pub.get("n_folds_h3"),
        "beats_seasonal_naive": pub.get("beats_seasonal_naive"),
        "reason": pub.get("reason"),
    }
    df = pd.DataFrame([row])
    if lb_path.exists() and lb_path.stat().st_size > 0:
        old = pd.read_csv(lb_path)
        old = old[old["model"] != model_id]
        df = pd.concat([old, df], ignore_index=True)
    rank = {"ok": 0, "not_competitive": 1, "skipped": 2}
    df = df.assign(_r=df["status"].map(rank).fillna(9)).sort_values(["_r", "rmse_h12"], na_position="last").drop(columns="_r")
    df.to_csv(lb_path, index=False)
    print(f"  saved {dest} status={pub.get('status')} rmse_h12={pub.get('rmse')}", flush=True)


def run_one(model_id: str, fn) -> dict:
    print(f"\n=== {model_id} ===", flush=True)
    try:
        m = fn()
    except Exception as e:  # noqa: BLE001
        m = {"model": model_id, "status": "skipped", "reason": f"{type(e).__name__}: {e}"}
        print(m["reason"], flush=True)
        print(traceback.format_exc(), flush=True)
    if not isinstance(m, dict):
        m = {"model": model_id, "status": "skipped", "reason": "trainer returned non-dict"}
    save_bundle(model_id, m)
    return m


def _jobs():
    from src.modeling.platinum2.trainers import (
        fit_arima,
        fit_holt,
        fit_ma3,
        fit_naive,
        fit_ridge_lags,
        fit_seasonal_naive,
        fit_timesfm,
    )

    return [
        ("seasonal_naive", fit_seasonal_naive),
        ("naive", fit_naive),
        ("ma3", fit_ma3),
        ("holt", fit_holt),
        ("arima", fit_arima),
        ("ridge_lags", fit_ridge_lags),
        ("timesfm", fit_timesfm),
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = _jobs()
    if args.only:
        wanted = set(args.only)
        jobs = [(k, fn) for k, fn in jobs if k in wanted]
    for model_id, fn in jobs:
        run_one(model_id, fn)
    print("\nleaderboard", RESULTS_ROOT / "leaderboard.csv", flush=True)
    if (RESULTS_ROOT / "leaderboard.csv").exists():
        print(pd.read_csv(RESULTS_ROOT / "leaderboard.csv").to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
