"""Default XGBoost baseline on tree_v1_* (NaNs retained, no scaling)."""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.model_registry import (
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)


def fit_xgboost_eval(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    model_name: str = "xgboost",
    save: bool = True,
    matrix_prefix: str = "tree_v1",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from xgboost import XGBClassifier
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"xgboost not installed: {e}"}

    X_tr, y_tr, _ = load_xy(matrix_prefix, "train")
    X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
    drop = [c for c in (drop_cols or []) if c in X_tr.columns]
    if drop:
        X_tr = X_tr.drop(columns=drop)
        X_va = X_va.drop(columns=drop)
    X_tr = X_tr.apply(pd.to_numeric, errors="coerce")
    X_va = X_va.apply(pd.to_numeric, errors="coerce")
    capacity = load_capacity_mw(meta_va)

    base = {
        "objective": "binary:logistic",
        "tree_method": "hist",
        "n_estimators": 3000,
        "learning_rate": 0.05,
        "max_depth": 4,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "logloss",
        "random_state": 42,
        "n_jobs": 4,
    }
    if params:
        base.update(params)
    early = int(base.pop("early_stopping_rounds", 100))
    model = XGBClassifier(**base, early_stopping_rounds=early)
    model.fit(
        X_tr,
        y_tr.astype(int),
        eval_set=[(X_va, y_va.astype(int))],
        verbose=False,
    )
    proba = model.predict_proba(X_va)[:, 1]
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update(
        {
            "status": "ok",
            "model": model_name,
            "split": SELECTION_SPLIT,
            "best_iteration": int(getattr(model, "best_iteration", base.get("n_estimators", 0))),
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
            hyperparams={**base, "early_stopping_rounds": early},
            feature_list=feature_list_from_X(X_tr),
            train_metadata={
                "matrix": matrix_prefix,
                "n_train": int(len(X_tr)),
                "n_val": int(len(X_va)),
                "prevalence_train": float(y_tr.mean()),
                "prevalence_val": float(y_va.mean()),
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
    return metrics


def train_xgboost_default() -> dict[str, Any]:
    return fit_xgboost_eval(model_name="xgboost", save=True)
