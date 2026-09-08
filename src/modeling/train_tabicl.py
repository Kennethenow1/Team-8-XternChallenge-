"""TabICLv2 default (pretrained ICL) on foundation_v1_*."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, classification_metrics
from src.modeling.model_registry import feature_list_from_X, load_xy, save_run_artifacts


def train_tabicl_default() -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from tabicl import TabICLClassifier
    except ImportError as e:
        return {"model": "tabicl", "status": "skipped", "reason": f"tabicl not installed: {e}"}

    X_tr, y_tr, _ = load_xy("foundation_v1", "train")
    X_va, y_va, meta_va = load_xy("foundation_v1", SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask], y_tr.loc[mask]

    # sklearn encoders inside TabICL reject mixed NAType/str
    for df in (X_tr, X_va):
        for c in df.columns:
            if df[c].dtype == object or str(df[c].dtype) == "string" or str(df[c].dtype).startswith("category"):
                df[c] = df[c].astype("string").fillna("__MISSING__").astype(str)
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    params = {"n_estimators": 8, "random_state": 42}
    try:
        model = TabICLClassifier(**params)
    except TypeError:
        model = TabICLClassifier()
        params = {"defaults": True}

    try:
        model.fit(X_tr, y_tr.astype(int))
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_va)[:, 1]
        else:
            pred = model.predict(X_va)
            proba = pred.astype(float)
    except Exception as e:  # noqa: BLE001 — surface as skip on leaderboard
        return {"model": "tabicl", "status": "skipped", "reason": str(e)}

    metrics = classification_metrics(y_va.astype(float), proba)
    metrics.update({"status": "ok", "model": "tabicl", "split": SELECTION_SPLIT})
    preds = meta_va.copy()
    preds["y_true"] = y_va.to_numpy()
    preds["y_prob"] = proba
    save_run_artifacts(
        "tabicl",
        hyperparams=params,
        feature_list=feature_list_from_X(X_tr),
        train_metadata={
            "matrix": "foundation_v1",
            "n_train": int(len(X_tr)),
            "n_val": int(len(X_va)),
            "prevalence_train": float(y_tr.mean()),
        },
        metrics=metrics,
        val_predictions=preds,
        model_obj=model,
    )
    return metrics
