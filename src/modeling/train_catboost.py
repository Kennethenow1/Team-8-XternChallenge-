"""Default CatBoost baseline on catboost_native_v1_*."""

from __future__ import annotations

from typing import Any, Sequence

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

    task = str(base_params.get("task_type", "GPU")).upper()
    # PRAUC/AUC custom metrics are not implemented on GPU and can distort early stopping.
    fit_kwargs: dict[str, Any] = {}
    if task != "GPU":
        fit_kwargs["custom_metric"] = ["PRAUC", "AUC"]

    model = CatBoostClassifier(**base_params, **fit_kwargs)
    model.fit(
        X_tr,
        y_tr.astype(int),
        cat_features=cat_cols,
        eval_set=(X_va, y_va.astype(int)),
        use_best_model=True,
    )
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
        }
    )
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
    return metrics


def train_catboost_default() -> dict[str, Any]:
    return fit_catboost_eval(model_name="catboost", save=True)


def train_catboost_v1_minus_macro() -> dict[str, Any]:
    return fit_catboost_eval(
        drop_cols=MACRO_FAMILY,
        model_name="catboost_v1_minus_macro",
        save=True,
    )
