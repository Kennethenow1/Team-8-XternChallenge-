"""LightGBM trainer + eval on tree_v1_* (val-only)."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.model_registry import (
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)
from src.modeling.train_catboost import _capacity_sample_weight


def fit_lightgbm_eval(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    add_cols: Sequence[str] | None = None,
    model_name: str = "lightgbm",
    save: bool = True,
    matrix_prefix: str = "tree_v1",
    sample_weight: np.ndarray | Sequence[float] | None = None,
    sample_weight_from: str | None = None,
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        import lightgbm as lgb
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"lightgbm not installed: {e}"}

    X_tr, y_tr, meta_tr = load_xy(matrix_prefix, "train")
    X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
    meta_tr = meta_tr.loc[mask]

    join_note: str | None = None
    if add_cols:
        from src.modeling.ablation_helpers import join_extra_feature_columns

        X_tr, added_tr, note_tr = join_extra_feature_columns(X_tr, meta_tr, add_cols, "train")
        X_va, added_va, note_va = join_extra_feature_columns(X_va, meta_va, add_cols, SELECTION_SPLIT)
        if not added_tr and not added_va:
            return {
                "model": model_name,
                "status": "skipped",
                "reason": note_tr or note_va or f"add_cols unavailable: {list(add_cols)}",
                "ablation": model_name,
            }
        join_note = note_tr or note_va

    drop = [c for c in (drop_cols or []) if c in X_tr.columns]
    if drop:
        X_tr = X_tr.drop(columns=drop)
        X_va = X_va.drop(columns=drop)
    X_tr = X_tr.apply(pd.to_numeric, errors="coerce")
    X_va = X_va.apply(pd.to_numeric, errors="coerce")
    capacity = load_capacity_mw(meta_va)

    weight: np.ndarray | None = None
    if sample_weight is not None:
        weight = np.asarray(sample_weight, dtype=float)
    elif sample_weight_from == "capacity_mw":
        weight = _capacity_sample_weight(meta_tr)

    base = {
        "objective": "binary",
        "metric": "binary_logloss",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 5,
        "min_child_samples": 20,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.0,
        "reg_lambda": 1.0,
        "n_estimators": 3000,
        "random_state": 42,
        "n_jobs": 4,
        "verbosity": -1,
    }
    if params:
        base.update(params)
    early = int(base.pop("early_stopping_rounds", 100))
    model = lgb.LGBMClassifier(**base)
    fit_kw: dict[str, Any] = {
        "eval_set": [(X_tr, y_tr.astype(int)), (X_va, y_va.astype(int))],
        "eval_names": ["train", "val"],
        "callbacks": [lgb.early_stopping(early, verbose=False), lgb.log_evaluation(period=0)],
    }
    if weight is not None:
        fit_kw["sample_weight"] = weight
    model.fit(X_tr, y_tr.astype(int), **fit_kw)
    proba = model.predict_proba(X_va)[:, 1]
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update({
        "status": "ok",
        "model": model_name,
        "split": SELECTION_SPLIT,
        "best_iteration": int(getattr(model, "best_iteration_", base.get("n_estimators", 0))),
        "added_features": list(add_cols or []),
        "join_note": join_note,
        "n_features": int(X_tr.shape[1]),
        "sample_weight_from": sample_weight_from,
    })
    history: list[dict[str, float]] = []
    try:
        ev = model.evals_result_
        tr_loss = ev.get("train", {}).get("binary_logloss") or []
        va_loss = ev.get("val", {}).get("binary_logloss") or ev.get("valid_1", {}).get("binary_logloss") or []
        tr_err = ev.get("train", {}).get("binary_error") or []
        va_err = ev.get("val", {}).get("binary_error") or ev.get("valid_1", {}).get("binary_error") or []
        n = max(len(tr_loss), len(va_loss), 0)
        for i in range(n):
            row: dict[str, float] = {"step": float(i)}
            if i < len(tr_loss):
                row["train_loss"] = float(tr_loss[i])
            if i < len(tr_err):
                row["train_acc"] = float(1.0 - tr_err[i])
            if i < len(va_loss):
                row["val_loss"] = float(va_loss[i])
            if i < len(va_err):
                row["val_acc"] = float(1.0 - va_err[i])
            history.append(row)
    except Exception:
        history = []
    metrics["history"] = history
    if save:
        preds = meta_va.copy()
        preds["y_true"] = y_va.to_numpy()
        preds["y_prob"] = proba
        preds["capacity_mw"] = capacity.to_numpy()
        save_run_artifacts(
            model_name,
            hyperparams={**base, "early_stopping_rounds": early},
            feature_list=feature_list_from_X(X_tr),
            train_metadata={
                "matrix": matrix_prefix,
                "n_train": int(len(X_tr)),
                "n_val": int(len(X_va)),
                "prevalence_train": float(y_tr.mean()),
                "prevalence_val": float(y_va.mean()),
                "added_features": list(add_cols or []),
                "join_note": join_note,
            },
            metrics=metrics,
            val_predictions=preds,
            model_obj=model,
        )
    else:
        metrics["_proba"] = proba
        metrics["_model"] = model
        metrics["_params"] = {**base, "early_stopping_rounds": early}
        metrics["_feature_list"] = feature_list_from_X(X_tr)
        metrics["_meta_va"] = meta_va
        metrics["_y_va"] = y_va
        metrics["_capacity"] = capacity
        metrics["_history"] = history
    return metrics


def train_lightgbm_default() -> dict[str, Any]:
    return fit_lightgbm_eval(model_name="lightgbm", save=True)
