"""TabPFN-3 default on foundation_v1_* (research; check commercial license separately)."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, classification_metrics
from src.modeling.model_registry import feature_list_from_X, load_xy, save_run_artifacts


def _load_tabpfn_token() -> None:
    """Load TABPFN_TOKEN from repo-root .env if not already in the environment."""
    if os.environ.get("TABPFN_TOKEN", "").strip():
        return
    try:
        from src.enrichment.env import load_enrichment_env

        load_enrichment_env()
    except Exception:
        pass


def train_tabpfn_default() -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    _load_tabpfn_token()
    if not os.environ.get("TABPFN_TOKEN", "").strip():
        return {
            "model": "tabpfn",
            "status": "skipped",
            "reason": (
                "TABPFN_TOKEN not set. Add TABPFN_TOKEN=... to repo-root .env "
                "(or export TABPFN_TOKEN=...), then re-run."
            ),
        }
    try:
        from tabpfn import TabPFNClassifier
    except ImportError as e:
        return {"model": "tabpfn", "status": "skipped", "reason": f"tabpfn not installed: {e}"}

    X_tr, y_tr, _ = load_xy("foundation_v1", "train")
    X_va, y_va, meta_va = load_xy("foundation_v1", SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask], y_tr.loc[mask]

    # Prefer string cats as-is; TabPFN handles mixed types in recent APIs
    params: dict[str, Any] = {"n_estimators": 8, "random_state": 42}
    try:
        model = TabPFNClassifier(**params)
    except TypeError:
        try:
            model = TabPFNClassifier(n_estimators=8)
            params = {"n_estimators": 8}
        except Exception as e:  # noqa: BLE001
            return {"model": "tabpfn", "status": "skipped", "reason": str(e)}

    try:
        model.fit(X_tr, y_tr.astype(int))
        proba = model.predict_proba(X_va)[:, 1]
    except Exception as e:  # noqa: BLE001
        return {"model": "tabpfn", "status": "skipped", "reason": str(e)}

    metrics = classification_metrics(y_va.astype(float), proba)
    metrics.update({"status": "ok", "model": "tabpfn", "split": SELECTION_SPLIT})
    preds = meta_va.copy()
    preds["y_true"] = y_va.to_numpy()
    preds["y_prob"] = proba
    save_run_artifacts(
        "tabpfn",
        hyperparams=params,
        feature_list=feature_list_from_X(X_tr),
        train_metadata={
            "matrix": "foundation_v1",
            "n_train": int(len(X_tr)),
            "n_val": int(len(X_va)),
            "prevalence_train": float(y_tr.mean()),
            "license_note": "TabPFN-3 weights may be non-commercial; research use only until reviewed.",
        },
        metrics=metrics,
        val_predictions=preds,
        model_obj=model,
    )
    return metrics
