"""LightGBM MAE regressor on delay_tree_v1."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.delay.common import history_from_evals, labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

LGBM_DELAY_DEFAULT: dict[str, Any] = {
    "objective": "mae",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 40,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "n_estimators": 5000,
    "early_stopping_rounds": 100,
    "random_state": 42,
}


def fit_lightgbm_delay(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    seed: int = 42,
    model_name: str = "lightgbm",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        import lightgbm as lgb
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"lightgbm not installed: {e}"}

    X_tr, y_tr, meta_tr = load_xy("delay_tree_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_tree_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr = X_tr.loc[mtr].apply(pd.to_numeric, errors="coerce")
    y_tr = y_tr.loc[mtr]
    X_va = X_va.loc[mva].apply(pd.to_numeric, errors="coerce")
    y_va, meta_va = y_va.loc[mva], meta_va.loc[mva]
    X_tr.columns = [str(c).replace(" ", "_") for c in X_tr.columns]
    X_va.columns = [str(c).replace(" ", "_") for c in X_va.columns]
    if drop_cols:
        drop = [str(c).replace(" ", "_") for c in drop_cols]
        X_tr = X_tr.drop(columns=[c for c in drop if c in X_tr.columns], errors="ignore")
        X_va = X_va.drop(columns=[c for c in drop if c in X_va.columns], errors="ignore")
    cfg = {**LGBM_DELAY_DEFAULT, **(params or {}), "random_state": int(seed), "verbose": -1}
    early = int(cfg.pop("early_stopping_rounds", 100))
    model = lgb.LGBMRegressor(**cfg)
    model.fit(
        X_tr,
        y_tr.astype(float),
        eval_set=[(X_va, y_va.astype(float))],
        eval_metric="l1",
        callbacks=[lgb.early_stopping(early, verbose=False), lgb.log_evaluation(0)],
    )
    best = int(getattr(model, "best_iteration_", 0) or 0)
    if best < 20:
        cfg["objective"] = "huber"
        cfg["n_estimators"] = max(int(cfg.get("n_estimators", 5000)), 800)
        model = lgb.LGBMRegressor(**cfg)
        model.fit(
            X_tr,
            y_tr.astype(float),
            eval_set=[(X_va, y_va.astype(float))],
            eval_metric="l1",
            callbacks=[lgb.early_stopping(max(early, 80), verbose=False), lgb.log_evaluation(0)],
        )
        best = int(getattr(model, "best_iteration_", 0) or 0)
    pred = model.predict(X_va)
    ev = model.evals_result_ or {}
    va = (ev.get("valid_0") or ev.get("valid_1") or {}).get("l1") or []
    tr = (ev.get("training") or {}).get("l1") or []
    hist = history_from_evals(tr, va, train_mae=tr, val_mae=va)
    extra = {"n_features": int(X_tr.shape[1]), "best_iteration": int(best), "_model": model}
    return pack_metrics(model=model_name, y_va=y_va, pred=np.asarray(pred, dtype=float), meta_va=meta_va, history=hist, extra=extra)
