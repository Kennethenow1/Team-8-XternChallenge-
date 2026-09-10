"""Default CatBoost baseline on catboost_native_v1_*."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.feature_policy import MACRO_FAMILY
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.model_registry import (
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)

# Freeze / trial-149 deploy recipe (docs/final_model_freeze.md). No scaler, no PCA.
CATBOOST_TRIAL_149: dict[str, Any] = {
    "depth": 5,
    "learning_rate": 0.1324314134827593,
    "l2_leaf_reg": 1.9470294574701563,
    "random_strength": 2.900625533346776,
    "bagging_temperature": 3.703566521912387,
    "border_count": 214,
    "min_data_in_leaf": 32,
    "iterations": 5000,
    "early_stopping_rounds": 100,
    "random_seed": 2026,
}


def _evals_to_history(evals: dict[str, Any]) -> list[dict[str, float]]:
    """Map CatBoost get_evals_result() into electrum history rows."""
    learn = evals.get("learn") or evals.get("training") or {}
    valid = evals.get("validation") or evals.get("val") or {}
    train_loss = learn.get("Logloss") or learn.get("logloss") or []
    val_loss = valid.get("Logloss") or valid.get("logloss") or []
    train_acc = learn.get("Accuracy") or learn.get("accuracy")
    val_acc = valid.get("Accuracy") or valid.get("accuracy")
    val_pr = valid.get("PRAUC") or valid.get("PRAUC:type=Classic")
    n = max(len(train_loss), len(val_loss), 0)
    rows: list[dict[str, float]] = []
    for i in range(n):
        row: dict[str, float] = {"step": float(i)}
        if i < len(train_loss):
            row["train_loss"] = float(train_loss[i])
        if train_acc is not None and i < len(train_acc):
            row["train_acc"] = float(train_acc[i])
        if i < len(val_loss):
            row["val_loss"] = float(val_loss[i])
        if val_acc is not None and i < len(val_acc):
            row["val_acc"] = float(val_acc[i])
        if val_pr is not None and i < len(val_pr):
            row["val_pr_auc"] = float(val_pr[i])
        rows.append(row)
    return rows


def _capacity_sample_weight(meta: pd.DataFrame) -> np.ndarray:
    w = pd.to_numeric(load_capacity_mw(meta), errors="coerce").to_numpy(dtype=float)
    w = np.where(np.isfinite(w) & (w > 0), w, np.nan)
    med = float(np.nanmedian(w)) if np.isfinite(w).any() else 1.0
    if not np.isfinite(med) or med <= 0:
        med = 1.0
    w = np.where(np.isfinite(w), w, med)
    mean = float(w.mean()) or 1.0
    return w / mean


def _prep_cats(X_tr: pd.DataFrame, X_va: pd.DataFrame) -> list[str]:
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    for c in cat_cols:
        X_tr[c] = X_tr[c].astype("string").fillna("__MISSING__")
        X_va[c] = X_va[c].astype("string").fillna("__MISSING__")
    return cat_cols


def fit_catboost_eval(
    *,
    drop_cols: Sequence[str] | None = None,
    add_cols: Sequence[str] | None = None,
    sys_fc_table: pd.DataFrame | None = None,
    sys_fc_cols: Sequence[str] | None = None,
    params: dict[str, Any] | None = None,
    model_name: str = "catboost",
    save: bool = True,
    matrix_prefix: str = "catboost_native_v1",
    sample_weight: np.ndarray | Sequence[float] | None = None,
    sample_weight_from: str | None = None,
    monotone_constraints: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Train CatBoost on train, evaluate on val with full metric bundle (+ ops)."""
    assert_selection_split(SELECTION_SPLIT)
    try:
        from catboost import CatBoostClassifier
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"catboost not installed: {e}"}

    X_tr, y_tr, meta_tr = load_xy(matrix_prefix, "train")
    X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
    meta_tr = meta_tr.loc[mask]

    join_note: str | None = None
    added_features: list[str] = list(add_cols or [])
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
        added_features = list(dict.fromkeys([*added_tr, *added_va]))

    if sys_fc_table is not None:
        from src.modeling.train_timesfm import join_system_forecast_features

        want = list(sys_fc_cols) if sys_fc_cols is not None else None
        X_tr, added_tr, note_tr = join_system_forecast_features(X_tr, meta_tr, sys_fc_table, want)
        X_va, added_va, note_va = join_system_forecast_features(X_va, meta_va, sys_fc_table, want)
        if not added_tr and not added_va:
            return {
                "model": model_name,
                "status": "skipped",
                "reason": note_tr or note_va or "sys_fc join failed",
                "ablation": model_name,
            }
        join_note = "; ".join(n for n in (join_note, note_tr or note_va) if n)
        added_features = list(dict.fromkeys([*added_features, *added_tr, *added_va]))

    drop = [c for c in (drop_cols or []) if c in X_tr.columns]
    if drop:
        X_tr = X_tr.drop(columns=drop)
        X_va = X_va.drop(columns=drop)

    cat_cols = _prep_cats(X_tr, X_va)
    capacity = load_capacity_mw(meta_va)

    weight: np.ndarray | None = None
    if sample_weight is not None:
        weight = np.asarray(sample_weight, dtype=float)
    elif sample_weight_from == "capacity_mw":
        weight = _capacity_sample_weight(meta_tr)

    base_params: dict[str, Any] = {
        "loss_function": "Logloss",
        "eval_metric": "Logloss",
        "iterations": 3000,
        "early_stopping_rounds": 100,
        "random_seed": 42,
        "verbose": False,
        "allow_writing_files": False,
        "task_type": "GPU",
        "devices": "0",
    }
    if params:
        base_params.update(params)
        # Drop GPU-only keys when forcing CPU (None values break CatBoost).
        if str(base_params.get("task_type", "")).upper() == "CPU":
            base_params.pop("devices", None)
            for k in list(base_params):
                if base_params[k] is None:
                    base_params.pop(k)

    if monotone_constraints:
        mono = [int(monotone_constraints.get(c, 0)) for c in X_tr.columns]
        if any(v != 0 for v in mono):
            base_params["monotone_constraints"] = mono

    def _cpu_params(p: dict[str, Any]) -> dict[str, Any]:
        out = dict(p)
        out["task_type"] = "CPU"
        out.pop("devices", None)
        for k in list(out):
            if out[k] is None:
                out.pop(k)
        return out

    def _fit(p: dict[str, Any]):
        task = str(p.get("task_type", "GPU")).upper()
        # PRAUC/AUC/Accuracy custom metrics are not implemented on GPU.
        extra: dict[str, Any] = {}
        if task != "GPU":
            extra["custom_metric"] = ["PRAUC", "AUC", "Accuracy"]
        clf = CatBoostClassifier(**p, **extra)
        fit_kw: dict[str, Any] = {
            "cat_features": cat_cols,
            "eval_set": (X_va, y_va.astype(int)),
            "use_best_model": True,
        }
        if weight is not None:
            fit_kw["sample_weight"] = weight
        clf.fit(X_tr, y_tr.astype(int), **fit_kw)
        return clf

    try:
        model = _fit(base_params)
    except Exception:
        if str(base_params.get("task_type", "")).upper() == "GPU":
            base_params = _cpu_params(base_params)
            model = _fit(base_params)
        else:
            raise
    proba = model.predict_proba(X_va)[:, 1]
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update(
        {
            "status": "ok",
            "model": model_name,
            "split": SELECTION_SPLIT,
            "best_iteration": int(getattr(model, "best_iteration_", model.tree_count_)),
            "dropped_features": drop,
            "added_features": added_features,
            "join_note": join_note,
            "n_features": int(X_tr.shape[1]),
            "sample_weight_from": sample_weight_from,
            "task_type": str(base_params.get("task_type")),
        }
    )
    history: list[dict[str, float]] = []
    try:
        history = _evals_to_history(model.get_evals_result())
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
            hyperparams={**base_params, "cat_features": cat_cols, "dropped_features": drop},
            feature_list=feature_list_from_X(X_tr),
            train_metadata={
                "matrix": matrix_prefix,
                "n_train": int(len(X_tr)),
                "n_val": int(len(X_va)),
                "prevalence_train": float(y_tr.mean()),
                "prevalence_val": float(y_va.mean()),
                "dropped_features": drop,
                "added_features": added_features,
                "join_note": join_note,
            },
            metrics=metrics,
            val_predictions=preds,
            model_obj=model,
            model_filename="model.cbm.joblib",
        )
    else:
        metrics["_proba"] = proba
        metrics["_model"] = model
        metrics["_params"] = base_params
        metrics["_feature_list"] = feature_list_from_X(X_tr)
        metrics["_meta_va"] = meta_va
        metrics["_y_va"] = y_va
        metrics["_capacity"] = capacity
        metrics["_X_tr"] = X_tr
        metrics["_X_va"] = X_va
        metrics["_history"] = history
        metrics["_cat_cols"] = cat_cols
    return metrics


def train_catboost_default() -> dict[str, Any]:
    return fit_catboost_eval(model_name="catboost", save=True)


def train_catboost_v1_minus_macro() -> dict[str, Any]:
    return fit_catboost_eval(
        drop_cols=MACRO_FAMILY,
        model_name="catboost_v1_minus_macro",
        save=True,
    )
