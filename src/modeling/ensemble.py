"""Weighted / mean ensembles of validation probabilities (val-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.modeling.eval_protocol import (
    SELECTION_SPLIT,
    assert_selection_split,
    combine_probabilities,
    full_eval_metrics,
)
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs, load_capacity_mw

ENSEMBLE_DIR = ARTIFACTS_DIR / "ensemble"
Objective = Literal["pr_auc", "log_loss"]


def load_aligned_val_probs(model_names: list[str]) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Load val predictions aligned on project_key + observation_date."""
    frames: list[pd.DataFrame] = []
    for name in model_names:
        path = ARTIFACTS_DIR / "models" / name / "val_predictions.parquet"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_parquet(path)
        keys = [c for c in ("project_key", "observation_date") if c in df.columns]
        if len(keys) < 2:
            raise ValueError(f"{name}: need project_key and observation_date for alignment")
        sub = df[keys + ["y_true", "y_prob"]].copy()
        sub = sub.rename(columns={"y_prob": name})
        frames.append(sub)

    merged = frames[0]
    for sub in frames[1:]:
        merged = merged.merge(sub, on=["project_key", "observation_date"], how="inner", suffixes=("", "_dup"))
        if "y_true_dup" in merged.columns:
            merged = merged.drop(columns=["y_true_dup"])

    y_true = merged["y_true"]
    meta = merged[["project_key", "observation_date"]].copy()
    prob_cols = merged[model_names]
    return prob_cols, y_true, meta


def equal_weight_ensemble(prob_df: pd.DataFrame) -> np.ndarray:
    w = {c: 1.0 / len(prob_df.columns) for c in prob_df.columns}
    prob_by_model = {c: prob_df[c].to_numpy() for c in prob_df.columns}
    return combine_probabilities(prob_by_model, w)


def optimize_weights(
    prob_df: pd.DataFrame,
    y_true: np.ndarray,
    *,
    objective: Objective = "pr_auc",
) -> dict[str, float]:
    """Nonnegative weights summing to 1 via softmax reparameterization."""
    names = list(prob_df.columns)
    P = prob_df.to_numpy(dtype=float)
    yt = np.asarray(y_true, dtype=float)

    def softmax(z: np.ndarray) -> np.ndarray:
        e = np.exp(z - z.max())
        return e / e.sum()

    def neg_score(z: np.ndarray) -> float:
        w = softmax(z)
        pred = P @ w
        pred = np.clip(pred, 1e-7, 1.0 - 1e-7)
        if objective == "pr_auc":
            from sklearn.metrics import average_precision_score

            return -float(average_precision_score(yt, pred))
        from sklearn.metrics import log_loss

        return float(log_loss(yt, pred, labels=[0.0, 1.0]))

    z0 = np.zeros(len(names))
    res = minimize(neg_score, z0, method="L-BFGS-B")
    w_arr = softmax(res.x)
    return {n: float(w) for n, w in zip(names, w_arr)}


def build_ensemble(
    model_names: list[str],
    *,
    ensemble_name: str = "ensemble_val",
    objectives: tuple[Objective, ...] = ("pr_auc", "log_loss"),
    save: bool = True,
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    ensure_artifact_dirs()
    prob_df, y_true, meta = load_aligned_val_probs(model_names)
    capacity = load_capacity_mw(meta)

    equal_prob = equal_weight_ensemble(prob_df)
    equal_metrics = full_eval_metrics(y_true, equal_prob, capacity)

    out: dict[str, Any] = {
        "ensemble": ensemble_name,
        "models": model_names,
        "split": SELECTION_SPLIT,
        "test_sealed": True,
        "n_val": int(len(y_true)),
        "equal_weight": {
            "weights": {c: 1.0 / len(model_names) for c in model_names},
            "metrics": equal_metrics,
        },
        "optimized": {},
    }

    for obj in objectives:
        weights = optimize_weights(prob_df, y_true.to_numpy(), objective=obj)
        prob_by_model = {c: prob_df[c].to_numpy() for c in prob_df.columns}
        combined = combine_probabilities(prob_by_model, weights)
        metrics = full_eval_metrics(y_true, combined, capacity)
        out["optimized"][obj] = {"weights": weights, "metrics": metrics}

    if save:
        d = ENSEMBLE_DIR / ensemble_name
        d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        pred = meta.copy()
        pred["y_true"] = y_true.to_numpy()
        pred["y_prob_equal"] = equal_prob
        for obj in objectives:
            w = out["optimized"][obj]["weights"]
            pred[f"y_prob_opt_{obj}"] = combine_probabilities(
                {c: prob_df[c].to_numpy() for c in prob_df.columns}, w
            )
        pred.to_parquet(d / "val_predictions.parquet", index=False)

    return out


def write_ensemble_report(result: dict[str, Any], path: Path | None = None) -> Path:
    path = path or (ARTIFACTS_DIR / "metrics" / "ensemble_summary.md")
    lines = [
        "# Ensemble summary (validation only)",
        "",
        f"Models: `{result.get('models')}`",
        "",
        "## Equal weight",
        "",
    ]
    em = (result.get("equal_weight") or {}).get("metrics") or {}
    lines.append(
        f"- PR-AUC={em.get('pr_auc')} ROC={em.get('roc_auc')} Brier={em.get('brier')} "
        f"LogLoss={em.get('log_loss')} MW@10%={em.get('withdrawn_mw_capture_at_10pct')}"
    )
    lines.append("")
    for obj, block in (result.get("optimized") or {}).items():
        m = block.get("metrics") or {}
        w = block.get("weights") or {}
        lines.append(f"## Optimized ({obj})")
        lines.append(f"- Weights: `{w}`")
        lines.append(
            f"- PR-AUC={m.get('pr_auc')} Brier={m.get('brier')} LogLoss={m.get('log_loss')}"
        )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
