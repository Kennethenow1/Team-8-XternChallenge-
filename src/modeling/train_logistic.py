"""Default logistic baselines (L2 and Elastic-Net) on logistic_v1_*."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.model_registry import (
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)


def fit_logistic_eval(
    *,
    name: str = "logistic",
    penalty: str = "l2",
    C: float = 1.0,
    l1_ratio: float | None = None,
    max_iter: int = 10_000,
    save: bool = True,
    matrix_prefix: str = "logistic_v1",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    X_tr, y_tr, _ = load_xy(matrix_prefix, "train")
    X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask_tr = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask_tr], y_tr.loc[mask_tr]
    capacity = load_capacity_mw(meta_va)

    # sklearn>=1.8: use l1_ratio instead of deprecated penalty=
    if penalty == "l2" or (l1_ratio is not None and l1_ratio == 0.0):
        kwargs: dict[str, Any] = {
            "solver": "saga",
            "C": C,
            "max_iter": max_iter,
            "class_weight": None,
            "l1_ratio": 0.0,
        }
    else:
        kwargs = {
            "solver": "saga",
            "C": C,
            "max_iter": max_iter,
            "class_weight": None,
            "l1_ratio": l1_ratio if l1_ratio is not None else 0.5,
        }

    clf = LogisticRegression(**kwargs, random_state=42)
    clf.fit(X_tr, y_tr.astype(int))
    proba = clf.predict_proba(X_va)[:, 1]
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update(
        {
            "status": "ok",
            "model": name,
            "split": SELECTION_SPLIT,
            "n_features": int(X_tr.shape[1]),
        }
    )
    if save:
        preds = meta_va.copy()
        preds["y_true"] = y_va.to_numpy()
        preds["y_prob"] = proba
        preds["capacity_mw"] = capacity.to_numpy()
        save_run_artifacts(
            name,
            hyperparams={**kwargs, "penalty": penalty},
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
            model_obj=clf,
        )
    else:
        metrics["_proba"] = proba
        metrics["_model"] = clf
        metrics["_params"] = {**kwargs, "penalty": penalty}
        metrics["_feature_list"] = feature_list_from_X(X_tr)
        metrics["_meta_va"] = meta_va
        metrics["_y_va"] = y_va
        metrics["_capacity"] = capacity
    return metrics


def train_logistic_l2_default() -> dict[str, Any]:
    return fit_logistic_eval(name="logistic_l2", penalty="l2", save=True)


def train_logistic_elasticnet_default() -> dict[str, Any]:
    return fit_logistic_eval(name="logistic_elasticnet", penalty="elasticnet", l1_ratio=0.5, save=True)


def train_constant_baseline() -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    _, y_tr, _ = load_xy("logistic_v1", "train")
    _, y_va, meta_va = load_xy("logistic_v1", SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce").dropna()
    y_va = pd.to_numeric(y_va, errors="coerce")
    capacity = load_capacity_mw(meta_va)
    p = float(y_tr.mean())
    proba = np.full(len(y_va), p)
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics["status"] = "ok"
    metrics["model"] = "constant"
    metrics["split"] = SELECTION_SPLIT
    metrics["constant_p"] = p
    preds = meta_va.copy()
    preds["y_true"] = y_va.to_numpy()
    preds["y_prob"] = proba
    preds["capacity_mw"] = capacity.to_numpy()
    save_run_artifacts(
        "constant",
        hyperparams={"type": "constant_prevalence", "p": p},
        feature_list={"feature_columns": [], "n": 0},
        train_metadata={"n_train": int(len(y_tr)), "prevalence_train": p},
        metrics=metrics,
        val_predictions=preds,
        model_obj={"p": p},
    )
    return metrics
