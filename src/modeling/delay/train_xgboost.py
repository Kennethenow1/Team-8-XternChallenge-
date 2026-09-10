"""XGBoost MAE regressor on delay_tree_v1. Refuse best_iteration==0 as underfit."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.delay.common import history_from_evals, labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

XGB_DELAY_DEFAULT: dict[str, Any] = {
    "objective": "reg:absoluteerror",
    "tree_method": "hist",
    "learning_rate": 0.03,
    "max_depth": 5,
    "min_child_weight": 8,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "n_estimators": 5000,
    "early_stopping_rounds": 100,
    "random_state": 42,
    "n_jobs": 4,
}


def fit_xgboost_delay(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    seed: int = 42,
    model_name: str = "xgboost",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from xgboost import XGBRegressor
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"xgboost not installed: {e}"}

    X_tr, y_tr, _ = load_xy("delay_tree_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_tree_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr = X_tr.loc[mtr].apply(pd.to_numeric, errors="coerce"), y_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva].apply(pd.to_numeric, errors="coerce"), y_va.loc[mva], meta_va.loc[mva]
    if drop_cols:
        X_tr = X_tr.drop(columns=[c for c in drop_cols if c in X_tr.columns], errors="ignore")
        X_va = X_va.drop(columns=[c for c in drop_cols if c in X_va.columns], errors="ignore")

    def _fit(early: int, lr: float) -> Any:
        cfg = {**XGB_DELAY_DEFAULT, **(params or {}), "random_state": int(seed), "learning_rate": lr}
        cfg.pop("early_stopping_rounds", None)
        model = XGBRegressor(**cfg, early_stopping_rounds=early)
        model.fit(X_tr, y_tr.astype(float), eval_set=[(X_tr, y_tr.astype(float)), (X_va, y_va.astype(float))], verbose=False)
        return model

    early = int((params or {}).get("early_stopping_rounds", XGB_DELAY_DEFAULT["early_stopping_rounds"]))
    lr = float((params or {}).get("learning_rate", XGB_DELAY_DEFAULT["learning_rate"]))
    model = _fit(early, lr)
    best = int(getattr(model, "best_iteration", None) or getattr(model, "best_iteration_", 0) or 0)
    if best <= 20:
        model = _fit(200, max(lr, 0.05))
        best = int(getattr(model, "best_iteration", None) or getattr(model, "best_iteration_", 0) or 0)
        if best == 0:
            return {"model": model_name, "status": "skipped", "reason": "underfit: best_iteration==0 after retry"}
    pred = model.predict(X_va)
    try:
        ev = model.evals_result()
        tr = (ev.get("validation_0") or {}).get("mae") or (ev.get("validation_0") or {}).get("mae") or []
        va = (ev.get("validation_1") or {}).get("mae") or []
    except Exception:
        tr, va = [], []
    hist = history_from_evals(tr, va, train_mae=tr, val_mae=va)
    extra = {"n_features": int(X_tr.shape[1]), "best_iteration": best, "_model": model}
    return pack_metrics(model=model_name, y_va=y_va, pred=np.asarray(pred, dtype=float), meta_va=meta_va, history=hist, extra=extra)
