"""CatBoostRegressor MAE on delay_catboost_native_v1."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.delay.common import history_from_evals, labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.delay_feature_policy import NATIVE_CATEGORICALS
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

CATBOOST_DELAY_DEFAULT: dict[str, Any] = {
    "depth": 5,
    "learning_rate": 0.08,
    "l2_leaf_reg": 2.0,
    "random_strength": 1.0,
    "bagging_temperature": 1.0,
    "border_count": 128,
    "min_data_in_leaf": 32,
    "iterations": 5000,
    "early_stopping_rounds": 100,
    "random_seed": 42,
    "loss_function": "MAE",
    "eval_metric": "MAE",
}


def fit_catboost_delay(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    seed: int = 42,
    task_type: str = "CPU",
    model_name: str = "catboost",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from catboost import CatBoostRegressor
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"catboost not installed: {e}"}

    X_tr, y_tr, meta_tr = load_xy("delay_catboost_native_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_catboost_native_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr, meta_tr = X_tr.loc[mtr].copy(), y_tr.loc[mtr], meta_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva].copy(), y_va.loc[mva], meta_va.loc[mva]
    if drop_cols:
        X_tr = X_tr.drop(columns=[c for c in drop_cols if c in X_tr.columns], errors="ignore")
        X_va = X_va.drop(columns=[c for c in drop_cols if c in X_va.columns], errors="ignore")
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    for c in cat_cols:
        X_tr[c] = X_tr[c].astype("string").fillna("__MISSING__")
        X_va[c] = X_va[c].astype("string").fillna("__MISSING__")
    cfg = {**CATBOOST_DELAY_DEFAULT, **(params or {}), "random_seed": int(seed), "task_type": task_type}
    early = int(cfg.pop("early_stopping_rounds", 100))
    model = CatBoostRegressor(**cfg, verbose=False, allow_writing_files=False)
    model.fit(
        X_tr,
        y_tr.astype(float),
        eval_set=(X_va, y_va.astype(float)),
        cat_features=cat_cols,
        early_stopping_rounds=early,
        use_best_model=True,
    )
    pred = model.predict(X_va)
    ev = model.get_evals_result()
    learn = (ev.get("learn") or {}).get("MAE") or (ev.get("learn") or {}).get("mae") or []
    valid = (ev.get("validation") or {}).get("MAE") or (ev.get("validation") or {}).get("mae") or []
    hist = history_from_evals(learn, valid, train_mae=learn, val_mae=valid)
    extra = {
        "n_features": int(X_tr.shape[1]),
        "best_iteration": int(getattr(model, "best_iteration_", 0) or 0),
        "_model": model,
        "params": {**CATBOOST_DELAY_DEFAULT, **(params or {}), "random_seed": int(seed)},
    }
    return pack_metrics(model=model_name, y_va=y_va, pred=np.asarray(pred, dtype=float), meta_va=meta_va, history=hist, extra=extra)
