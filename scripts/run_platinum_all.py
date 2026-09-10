#!/usr/bin/env python3
"""Train every Platinum delay model and write platinum/results/ (val only; test sealed)."""

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

try:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
except Exception:
    pass

RESULTS_ROOT = REPO / "platinum" / "results"


def _public(m: dict) -> dict:
    skip = {"history", "folds", "companion_proba"}
    out = {}
    for k, v in m.items():
        if str(k).startswith("_") or k in skip:
            continue
        if k == "traceback":
            continue
        if isinstance(v, np.ndarray):
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v)
        elif isinstance(v, (float, int, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict) and k in {"baselines", "gia", "params", "hardware"}:
            try:
                json.dumps(v, default=str)
                out[k] = v
            except TypeError:
                out[k] = {kk: str(vv) for kk, vv in v.items()}
    return out


def _history(m: dict) -> pd.DataFrame:
    hist = m.get("history") or m.get("_history") or []
    if not hist:
        return pd.DataFrame(columns=["step", "train_loss", "val_loss", "train_mae", "val_mae"])
    return pd.DataFrame(hist)


def _write_plots(dest: Path, m: dict, hist: pd.DataFrame) -> None:
    try:
        import plotly.graph_objects as go
    except Exception as e:  # noqa: BLE001
        print(f"  plotly skipped: {e}", flush=True)
        return
    y = m.get("_y_va")
    pred = m.get("_pred")
    if y is not None and pred is not None:
        y = np.asarray(y, dtype=float).reshape(-1)
        pred = np.asarray(pred, dtype=float).reshape(-1)
        n = min(len(y), len(pred))
        pd.DataFrame({"y": y[:n], "pred": pred[:n]}).to_parquet(dest / "val_predictions.parquet", index=False)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=y[:n], y=pred[:n], mode="markers", name="val", opacity=0.45))
        lo = float(np.nanmin([y[:n].min(), pred[:n].min()])) if n else 0.0
        hi = float(np.nanmax([y[:n].max(), pred[:n].max()])) if n else 1.0
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="45°"))
        fig.update_layout(
            title=f"Val predicted vs actual COD slip (MAE={m.get('mae')})",
            xaxis_title="actual months",
            yaxis_title="predicted months",
        )
        fig.write_html(dest / "plots" / "val_pred_vs_actual.html")
    if not hist.empty:
        fig = go.Figure()
        for col, name in (
            ("train_loss", "train loss"),
            ("val_loss", "val loss"),
            ("train_mae", "train MAE"),
            ("val_mae", "val MAE"),
        ):
            if col in hist.columns:
                fig.add_trace(go.Scatter(x=hist.get("step"), y=hist[col], mode="lines", name=name))
        fig.update_layout(title="Train/val curves", xaxis_title="step")
        fig.write_html(dest / "plots" / "history.html")


def save_bundle(model_id: str, m: dict) -> None:
    dest = RESULTS_ROOT / model_id
    (dest / "models").mkdir(parents=True, exist_ok=True)
    (dest / "plots").mkdir(parents=True, exist_ok=True)
    pub = _public(m or {})
    pub.setdefault("model", model_id)
    pub.setdefault("status", m.get("status", "skipped") if m else "skipped")
    (dest / "metrics.json").write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")
    hist = _history(m or {})
    hist.to_csv(dest / "history.csv", index=False)
    _write_plots(dest, m or {}, hist)
    obj = (m or {}).get("_model")
    if obj is not None and pub.get("status") in {"ok", "not_competitive"}:
        try:
            import joblib

            joblib.dump(obj, dest / "models" / "model.joblib")
        except Exception as e:  # noqa: BLE001
            print(f"  joblib dump skipped: {e}", flush=True)
        try:
            if hasattr(obj, "save_model"):
                obj.save_model(str(dest / "models" / "model.cbm"))
        except Exception:
            pass
        try:
            import torch

            if isinstance(obj, torch.nn.Module):
                torch.save(obj.state_dict(), dest / "models" / "model.pt")
        except Exception:
            pass
        try:
            if hasattr(obj, "save") and hasattr(obj, "count_params"):
                obj.save(str(dest / "models" / "model.keras"))
        except Exception as e:  # noqa: BLE001
            print(f"  keras save skipped: {e}", flush=True)
    lb_path = RESULTS_ROOT / "leaderboard.csv"
    row = {
        "model": model_id,
        "run_name": pub.get("model", model_id),
        "split": "val",
        "status": pub.get("status"),
        "mae": pub.get("mae"),
        "rmse": pub.get("rmse"),
        "median_ae": pub.get("median_ae"),
        "pinball80": pub.get("pinball80"),
        "companion_pr_auc": pub.get("companion_pr_auc"),
        "delayed_mw_capture_at_10pct": pub.get("delayed_mw_capture_at_10pct"),
        "beats_persist_mae": pub.get("beats_persist_mae"),
        "n_features": pub.get("n_features"),
        "reason": pub.get("reason"),
    }
    df = pd.DataFrame([row])
    if lb_path.exists() and lb_path.stat().st_size > 0:
        old = pd.read_csv(lb_path)
        old = old[old["model"] != model_id]
        df = pd.concat([old, df], ignore_index=True)
    if "mae" in df.columns:
        rank = {"ok": 0, "not_competitive": 1, "skipped": 2}
        df = df.assign(_r=df["status"].map(rank).fillna(9)).sort_values(["_r", "mae"], na_position="last").drop(columns="_r")
    df.to_csv(lb_path, index=False)
    print(f"  saved {dest} status={pub.get('status')} mae={pub.get('mae')}", flush=True)


def run_one(model_id: str, fn) -> dict:
    print(f"\n=== {model_id} ===", flush=True)
    try:
        m = fn()
    except Exception as e:  # noqa: BLE001
        m = {"model": model_id, "status": "skipped", "reason": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        print(m["reason"], flush=True)
        print(m.get("traceback"), flush=True)
    if not isinstance(m, dict):
        m = {"model": model_id, "status": "skipped", "reason": "trainer returned non-dict"}
    save_bundle(model_id, m)
    return m


def _jobs():
    from src.modeling.delay.train_ridge import fit_ridge_eval
    from src.modeling.delay.train_catboost import fit_catboost_delay
    from src.modeling.delay.train_lightgbm import fit_lightgbm_delay
    from src.modeling.delay.train_xgboost import fit_xgboost_delay
    from src.modeling.delay.train_tabm import fit_tabm_delay
    from src.modeling.delay.train_ft_transformer import fit_ft_transformer_delay
    from src.modeling.delay.train_tabicl import fit_tabicl_delay
    from src.modeling.delay.train_tabpfn import fit_tabpfn_delay
    from src.modeling.delay.train_seq_cnn import fit_seq_cnn_delay
    from src.modeling.delay.train_nasnet import fit_nasnet_delay
    from src.modeling.delay.train_survival import fit_survival_delay
    from src.modeling.delay.train_timesfm import fit_timesfm_delay

    return [
        ("logistic", lambda: fit_ridge_eval()),
        ("catboost", lambda: fit_catboost_delay()),
        ("lightgbm", lambda: fit_lightgbm_delay()),
        ("xgboost", lambda: fit_xgboost_delay()),
        ("tabm", lambda: fit_tabm_delay(use_gpu=True, allow_cpu=True)),
        ("ft_transformer", lambda: fit_ft_transformer_delay(use_gpu=True)),
        ("tabicl", lambda: fit_tabicl_delay()),
        ("tabpfn", lambda: fit_tabpfn_delay()),
        ("seq_cnn", lambda: fit_seq_cnn_delay(max_epochs=100, patience=15, min_epochs=8)),
        ("survival", lambda: fit_survival_delay()),
        ("timesfm", lambda: fit_timesfm_delay()),
        ("nasnet_cnn", lambda: fit_nasnet_delay(do_finetune=True)),
    ]


def backfill_history_plots() -> None:
    for dest in sorted(RESULTS_ROOT.iterdir()):
        if not dest.is_dir():
            continue
        hist_path = dest / "history.csv"
        if not hist_path.exists() or hist_path.stat().st_size < 8:
            continue
        hist = pd.read_csv(hist_path)
        m: dict = {}
        metrics = dest / "metrics.json"
        if metrics.exists():
            try:
                m = json.loads(metrics.read_text(encoding="utf-8"))
            except Exception:
                m = {}
        pred_path = dest / "val_predictions.parquet"
        if pred_path.exists():
            try:
                pred_df = pd.read_parquet(pred_path)
                m["_y_va"] = pred_df["y"].to_numpy()
                m["_pred"] = pred_df["pred"].to_numpy()
            except Exception:
                pass
        _write_plots(dest, m, hist)
        print(f"  plots {dest.name}", flush=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None, help="Subset of model ids to run")
    parser.add_argument("--backfill-plots", action="store_true", help="Write history HTML from existing CSVs")
    args = parser.parse_args(argv)
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    if args.backfill_plots and not args.only:
        backfill_history_plots()
        return 0
    jobs = _jobs()
    if args.only:
        wanted = set(args.only)
        jobs = [(k, fn) for k, fn in jobs if k in wanted]
        missing = wanted - {k for k, _ in jobs}
        if missing:
            print(f"unknown --only ids: {sorted(missing)}", flush=True)
            return 2
    for model_id, fn in jobs:
        run_one(model_id, fn)
    print("\nleaderboard", RESULTS_ROOT / "leaderboard.csv", flush=True)
    if (RESULTS_ROOT / "leaderboard.csv").exists():
        print(pd.read_csv(RESULTS_ROOT / "leaderboard.csv").to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
