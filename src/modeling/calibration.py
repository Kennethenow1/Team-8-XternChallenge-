"""Probability calibration (Platt / isotonic) on validation predictions only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from src.modeling.eval_protocol import (
    SELECTION_SPLIT,
    assert_selection_split,
    calibration_curve_points,
    classification_metrics,
    full_eval_metrics,
)
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs, load_capacity_mw

CALIBRATION_DIR = ARTIFACTS_DIR / "calibration"
Method = Literal["platt", "isotonic"]


def _clip_prob(y_prob: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(y_prob, dtype=float), 1e-7, 1.0 - 1e-7)


def _fit_platt(y_true: np.ndarray, y_prob: np.ndarray) -> LogisticRegression:
    p = _clip_prob(y_prob)
    logit = np.log(p / (1.0 - p)).reshape(-1, 1)
    lr = LogisticRegression(C=1e10, solver="lbfgs", max_iter=1000)
    lr.fit(logit, y_true.astype(int))
    return lr


def _apply_platt(model: LogisticRegression, y_prob: np.ndarray) -> np.ndarray:
    p = _clip_prob(y_prob)
    logit = np.log(p / (1.0 - p)).reshape(-1, 1)
    return model.predict_proba(logit)[:, 1]


def _fit_isotonic(y_true: np.ndarray, y_prob: np.ndarray) -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(y_prob, y_true)
    return iso


def cross_fitted_calibration_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    method: Method,
    n_splits: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    """Primary metrics: out-of-fold calibrated probabilities on val (5-fold stratified)."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    if len(yt) < 20 or len(np.unique(yt)) < 2:
        return {"status": "skipped", "reason": "insufficient val rows for calibration CV"}

    oof = np.full(len(yt), np.nan)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for tr_idx, va_idx in skf.split(yp, yt.astype(int)):
        if method == "platt":
            cal = _fit_platt(yt[tr_idx], yp[tr_idx])
            oof[va_idx] = _apply_platt(cal, yp[va_idx])
        else:
            cal = _fit_isotonic(yt[tr_idx], yp[tr_idx])
            oof[va_idx] = cal.predict(yp[va_idx])

    m = classification_metrics(yt, oof)
    m.update(
        {
            "status": "ok",
            "method": method,
            "protocol": f"{n_splits}-fold stratified CV on val (primary)",
            "reliability": calibration_curve_points(yt, oof),
        }
    )
    return m


def fit_calibrator_on_val(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    method: Method,
) -> tuple[Any, dict[str, Any]]:
    """Fit calibrator on entire val (secondary / deployment artifact)."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    if method == "platt":
        model = _fit_platt(yt, yp)
        calibrated = _apply_platt(model, yp)
    else:
        model = _fit_isotonic(yt, yp)
        calibrated = model.predict(yp)
    metrics = classification_metrics(yt, calibrated)
    metrics.update(
        {
            "status": "ok",
            "method": method,
            "protocol": "fit on entire val (secondary; not for selection)",
            "reliability": calibration_curve_points(yt, calibrated),
        }
    )
    return model, metrics


def load_model_val_predictions(model_name: str) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    pred_path = ARTIFACTS_DIR / "models" / model_name / "val_predictions.parquet"
    if not pred_path.exists():
        raise FileNotFoundError(pred_path)
    df = pd.read_parquet(pred_path)
    if "y_true" not in df.columns or "y_prob" not in df.columns:
        raise ValueError(f"{pred_path} missing y_true / y_prob")
    return df["y_true"], df["y_prob"], df


def calibrate_model(
    model_name: str,
    *,
    methods: tuple[Method, ...] = ("platt", "isotonic"),
    n_splits: int = 5,
    save: bool = True,
) -> dict[str, Any]:
    """Calibrate finalist val predictions; primary = cross-fitted val metrics."""
    assert_selection_split(SELECTION_SPLIT)
    ensure_artifact_dirs()
    y_true, y_prob, meta = load_model_val_predictions(model_name)
    if "capacity_mw" in meta.columns:
        capacity = pd.to_numeric(meta["capacity_mw"], errors="coerce")
    else:
        capacity = load_capacity_mw(meta) if "project_key" in meta.columns else None

    out: dict[str, Any] = {
        "model": model_name,
        "split": SELECTION_SPLIT,
        "test_sealed": True,
        "n_val": int(len(y_true)),
        "methods": {},
    }
    best_method: str | None = None
    best_brier = float("inf")

    for method in methods:
        cv_m = cross_fitted_calibration_metrics(y_true.to_numpy(), y_prob.to_numpy(), method=method, n_splits=n_splits)
        calibrator, full_m = fit_calibrator_on_val(y_true.to_numpy(), y_prob.to_numpy(), method=method)
        if method == "isotonic":
            cal_full_prob = calibrator.predict(y_prob.to_numpy())
        else:
            cal_full_prob = _apply_platt(calibrator, y_prob.to_numpy())
        ops = full_eval_metrics(y_true, cal_full_prob, capacity)

        entry = {
            "cross_fitted_primary": {k: cv_m.get(k) for k in ("brier", "ece", "log_loss", "pr_auc", "roc_auc", "reliability", "protocol")},
            "full_val_fit": {k: full_m.get(k) for k in ("brier", "ece", "log_loss", "pr_auc", "roc_auc", "reliability", "protocol")},
            "full_val_ops": {
                k: ops.get(k)
                for k in (
                    "withdrawn_mw_capture_at_10pct",
                    "precision_at_10pct",
                    "recall_at_10pct",
                )
            },
            "raw_val": classification_metrics(y_true, y_prob),
        }
        out["methods"][method] = entry

        brier = float(cv_m.get("brier") or float("inf"))
        if brier < best_brier:
            best_brier = brier
            best_method = method

        if save:
            d = CALIBRATION_DIR / model_name / method
            d.mkdir(parents=True, exist_ok=True)
            joblib.dump(calibrator, d / "calibrator.joblib")
            (d / "metrics.json").write_text(json.dumps(entry, indent=2, default=str), encoding="utf-8")
            rel = entry["cross_fitted_primary"].get("reliability") or {}
            (d / "reliability_points.json").write_text(json.dumps(rel, indent=2), encoding="utf-8")

    out["best_method_by_cv_brier"] = best_method
    if save:
        root = CALIBRATION_DIR / model_name
        root.mkdir(parents=True, exist_ok=True)
        (root / "summary.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def write_calibration_report(results: list[dict[str, Any]], path: Path | None = None) -> Path:
    path = path or (ARTIFACTS_DIR / "metrics" / "calibration_summary.md")
    lines = [
        "# Calibration summary (validation only)",
        "",
        "**Primary metrics:** 5-fold cross-fitted calibration on val.",
        "**Secondary:** full-val fit (deployment artifact; not for selection).",
        "**Test / score sealed.**",
        "",
    ]
    for r in results:
        lines.append(f"## `{r.get('model')}`")
        lines.append("")
        for method, entry in (r.get("methods") or {}).items():
            prim = entry.get("cross_fitted_primary") or {}
            raw = entry.get("raw_val") or {}
            ops = entry.get("full_val_ops") or {}
            lines.append(f"### {method}")
            lines.append(
                f"- CV Brier={prim.get('brier')} ECE={prim.get('ece')} LogLoss={prim.get('log_loss')} "
                f"(raw Brier={raw.get('brier')})"
            )
            lines.append(
                f"- Full-val ops (deployment fit): P@10%={ops.get('precision_at_10pct')} "
                f"R@10%={ops.get('recall_at_10pct')} MW@10%={ops.get('withdrawn_mw_capture_at_10pct')}"
            )
        lines.append(f"- Best by CV Brier: `{r.get('best_method_by_cv_brier')}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
