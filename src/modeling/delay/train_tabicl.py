"""TabICL classifier on companion binary → P(slip)×E[delay|slip] as weak delay estimate."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy, y_binary
from src.modeling.delay_eval_protocol import persist_baseline
from src.modeling.delay_eval_protocol import regression_metrics
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split


def fit_tabicl_delay(*, n_estimators: int = 8, seed: int = 42, model_name: str = "tabicl") -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from tabicl import TabICLClassifier
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"tabicl not installed: {e}"}

    X_tr, y_tr, meta_tr = load_xy("delay_foundation_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_foundation_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr, meta_tr = X_tr.loc[mtr].copy(), y_tr.loc[mtr], meta_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva].copy(), y_va.loc[mva], meta_va.loc[mva]
    yb = y_binary(meta_tr).fillna(0).astype(int)
    for c in X_tr.columns:
        if X_tr[c].dtype == object or str(X_tr[c].dtype) == "string":
            X_tr[c] = X_tr[c].astype("string").fillna("__MISSING__")
            X_va[c] = X_va[c].astype("string").fillna("__MISSING__")
        else:
            X_tr[c] = pd.to_numeric(X_tr[c], errors="coerce")
            X_va[c] = pd.to_numeric(X_va[c], errors="coerce")
    clf = TabICLClassifier(n_estimators=int(n_estimators), random_state=int(seed))
    clf.fit(X_tr, yb)
    p = clf.predict_proba(X_va)[:, 1]
    cond = float(y_tr[yb.eq(1)].mean()) if (yb == 1).any() else float(y_tr.mean())
    pred = p * cond
    persist = persist_baseline(meta_va)
    persist_mae = regression_metrics(y_va, persist)["mae"]
    extra = {"n_features": int(X_tr.shape[1]), "conditional_mean_delay": cond, "_model": clf}
    m = pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, extra=extra)
    if np.isfinite(m.get("mae")) and np.isfinite(persist_mae) and m["mae"] > persist_mae:
        m["status"] = "not_competitive"
        m["reason"] = f"val MAE {m['mae']:.3f} worse than persist {persist_mae:.3f}"
    return m
