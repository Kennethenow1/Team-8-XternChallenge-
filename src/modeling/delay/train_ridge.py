"""Ridge / ElasticNet delay-months regression + companion logistic."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge

from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy, y_binary
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split


def fit_ridge_eval(
    *,
    alpha: float = 1.0,
    l1_ratio: float = 0.0,
    seed: int = 42,
    model_name: str = "logistic",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    X_tr, y_tr, meta_tr = load_xy("delay_logistic_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_logistic_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr, meta_tr = X_tr.loc[mtr], y_tr.loc[mtr], meta_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva], y_va.loc[mva], meta_va.loc[mva]
    X_tr = X_tr.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_va = X_va.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if l1_ratio and l1_ratio > 0:
        model = ElasticNet(alpha=float(alpha), l1_ratio=float(l1_ratio), max_iter=20000, random_state=int(seed))
    else:
        model = Ridge(alpha=float(alpha), random_state=int(seed))
    model.fit(X_tr, y_tr.astype(float))
    pred = model.predict(X_va)

    companion = None
    yb_tr = y_binary(meta_tr)
    yb_va = y_binary(meta_va)
    if yb_tr.notna().sum() > 10 and yb_tr.nunique() > 1:
        clf = LogisticRegression(solver="saga", max_iter=4000, C=1.0, random_state=int(seed))
        clf.fit(X_tr, yb_tr.fillna(0).astype(int))
        companion = clf.predict_proba(X_va)[:, 1]

    extra = {"n_features": int(X_tr.shape[1]), "alpha": alpha, "l1_ratio": l1_ratio, "_model": model}
    if companion is not None:
        extra["companion_proba"] = companion
    return pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, extra=extra)
