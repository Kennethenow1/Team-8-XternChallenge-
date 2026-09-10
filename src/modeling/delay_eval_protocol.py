"""Val-only evaluation for COD-slip regression. Test stays sealed."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

from src.common.paths import GOLD_DIR
from src.gold.cod_delay import NEURAL_NET_MIN_VAL_LABELED
from src.modeling.eval_protocol import SEALED_SPLITS, SELECTION_SPLIT, assert_selection_split

DELAY_DIR = GOLD_DIR / "delay"
SPLIT_MANIFEST = DELAY_DIR / "split_manifest.json"
PRIMARY_METRICS = ("mae", "rmse", "median_ae", "pinball50", "pinball80")


def load_delay_split_manifest() -> dict[str, Any]:
    if not SPLIT_MANIFEST.exists():
        return {}
    return json.loads(SPLIT_MANIFEST.read_text(encoding="utf-8"))


def neural_nets_allowed() -> bool:
    man = load_delay_split_manifest()
    if "neural_nets_ok" in man:
        return bool(man["neural_nets_ok"])
    return int(man.get("audit", {}).get("val_labeled") or 0) >= NEURAL_NET_MIN_VAL_LABELED


def pinball(y: np.ndarray, yhat: np.ndarray, q: float) -> float:
    y, yhat = np.asarray(y, dtype=float), np.asarray(yhat, dtype=float)
    mask = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[mask], yhat[mask]
    if len(y) == 0:
        return float("nan")
    e = y - yhat
    return float(np.mean(np.maximum(q * e, (q - 1.0) * e)))


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    yt = np.asarray(y_true, dtype=float).reshape(-1)
    yp = np.asarray(y_pred, dtype=float).reshape(-1)
    n = min(len(yt), len(yp))
    yt, yp = yt[:n], yp[:n]
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    out = {
        "n": float(len(yt)),
        "mae": float("nan"),
        "rmse": float("nan"),
        "median_ae": float("nan"),
        "pinball50": float("nan"),
        "pinball80": float("nan"),
        "mean_y": float("nan"),
        "mean_pred": float("nan"),
    }
    if len(yt) == 0:
        return out
    err = yp - yt
    out["mae"] = float(np.mean(np.abs(err)))
    out["rmse"] = float(np.sqrt(np.mean(err**2)))
    out["median_ae"] = float(np.median(np.abs(err)))
    out["pinball50"] = pinball(yt, yp, 0.5)
    out["pinball80"] = pinball(yt, yp, 0.8)
    out["mean_y"] = float(np.mean(yt))
    out["mean_pred"] = float(np.mean(yp))
    return out


def companion_metrics(y_bin, score) -> dict[str, float]:
    yt = np.asarray(y_bin, dtype=float)
    yp = np.asarray(score, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    out = {"pr_auc": float("nan"), "roc_auc": float("nan"), "log_loss": float("nan"), "prevalence": float("nan")}
    if len(yt) < 2 or len(np.unique(yt)) < 2:
        if len(yt):
            out["prevalence"] = float(yt.mean())
        return out
    yp_c = np.clip(yp, 1e-7, 1 - 1e-7)
    out["prevalence"] = float(yt.mean())
    out["pr_auc"] = float(average_precision_score(yt, yp_c))
    out["roc_auc"] = float(roc_auc_score(yt, yp_c))
    out["log_loss"] = float(log_loss(yt, yp_c, labels=[0.0, 1.0]))
    return out


def delayed_mw_capture(y_true, y_pred, capacity_mw, *, frac: float = 0.10) -> float:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mw = np.asarray(capacity_mw if capacity_mw is not None else np.ones(len(yt)), dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp, mw = yt[mask], yp[mask], np.where(np.isfinite(mw[mask]), mw[mask], 0.0)
    delayed = yt >= 12
    delayed_mw = float(mw[delayed].sum())
    if delayed_mw <= 0 or len(yt) == 0:
        return float("nan")
    k = max(1, int(np.ceil(frac * len(yt))))
    order = np.argsort(-yp)
    top = order[:k]
    return float(mw[top][yt[top] >= 12].sum() / delayed_mw)


def persist_baseline(meta: pd.DataFrame) -> np.ndarray:
    if "service_date_shift_months" in meta.columns:
        s = pd.to_numeric(meta["service_date_shift_months"], errors="coerce").to_numpy(dtype=float)
        med = float(np.nanmedian(s)) if np.isfinite(s).any() else 0.0
        return np.where(np.isfinite(s), s, med)
    return np.zeros(len(meta), dtype=float)


def baseline_metrics(y_true, meta: pd.DataFrame) -> dict[str, Any]:
    yt = pd.to_numeric(pd.Series(y_true), errors="coerce").to_numpy(dtype=float)
    zero = regression_metrics(yt, np.zeros_like(yt))
    mean = float(np.nanmean(yt)) if np.isfinite(yt).any() else 0.0
    mean_pred = regression_metrics(yt, np.full_like(yt, mean))
    persist = regression_metrics(yt, persist_baseline(meta))
    return {"zero_slip": zero, "train_mean": mean_pred, "persist_last_shift": persist, "train_mean_value": mean}


def full_delay_metrics(
    y_true,
    y_pred,
    *,
    y_bin=None,
    score_bin=None,
    capacity_mw=None,
    meta: pd.DataFrame | None = None,
    is_gia: np.ndarray | pd.Series | None = None,
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    out: dict[str, Any] = {"split": SELECTION_SPLIT, **regression_metrics(y_true, y_pred)}
    if y_bin is not None and score_bin is not None:
        out.update({f"companion_{k}": v for k, v in companion_metrics(y_bin, score_bin).items()})
    elif y_bin is not None:
        # threshold predicted months
        score = (np.asarray(y_pred, dtype=float) >= 12).astype(float)
        # use raw pred as ranking score
        out.update({f"companion_{k}": v for k, v in companion_metrics(y_bin, y_pred).items()})
        out["companion_thresholded_acc"] = float(np.mean(score == np.asarray(y_bin, dtype=float))) if np.isfinite(np.asarray(y_bin, dtype=float)).any() else float("nan")
    if capacity_mw is not None:
        out["delayed_mw_capture_at_10pct"] = delayed_mw_capture(y_true, y_pred, capacity_mw)
    if meta is not None:
        out["baselines"] = baseline_metrics(y_true, meta)
        persist_mae = out["baselines"]["persist_last_shift"]["mae"]
        mean_p80 = out["baselines"]["train_mean"]["pinball80"]
        out["beats_persist_mae"] = bool(np.isfinite(out["mae"]) and np.isfinite(persist_mae) and out["mae"] < persist_mae)
        out["beats_mean_pinball80"] = bool(np.isfinite(out["pinball80"]) and np.isfinite(mean_p80) and out["pinball80"] < mean_p80)
    if is_gia is not None:
        g = np.asarray(is_gia, dtype=bool)
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        if g.shape == yt.shape and g.any():
            out["gia"] = regression_metrics(yt[g], yp[g])
    return out
