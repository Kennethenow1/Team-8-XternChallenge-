"""TabPFNRegressor if available; else classifier-on-binary + conditional mean."""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy, y_binary
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split


def _load_tabpfn_token() -> None:
    if os.environ.get("TABPFN_TOKEN", "").strip():
        return
    try:
        from src.enrichment.env import load_enrichment_env

        load_enrichment_env()
    except Exception:
        pass


def fit_tabpfn_delay(*, n_estimators: int = 8, seed: int = 42, model_name: str = "tabpfn") -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    _load_tabpfn_token()
    try:
        from tabpfn import TabPFNRegressor  # noqa: F401
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"tabpfn not installed: {e}"}
    X_tr, y_tr, meta_tr = load_xy("delay_foundation_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_foundation_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr, meta_tr = X_tr.loc[mtr].copy(), y_tr.loc[mtr], meta_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva].copy(), y_va.loc[mva], meta_va.loc[mva]
    X_tr_n = X_tr.apply(pd.to_numeric, errors="coerce")
    X_va_n = X_va.apply(pd.to_numeric, errors="coerce")
    if len(X_tr) > 10_000:
        w = pd.to_numeric(meta_tr.get("capacity_mw"), errors="coerce").fillna(1.0).to_numpy()
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(X_tr), size=10_000, replace=False, p=w / w.sum())
        X_tr_n, y_tr = X_tr_n.iloc[idx], y_tr.iloc[idx]
        meta_tr = meta_tr.iloc[idx]

    try:
        from tabpfn import TabPFNRegressor

        model = TabPFNRegressor(n_estimators=int(n_estimators), random_state=int(seed))
        model.fit(X_tr_n.fillna(0), y_tr.astype(float))
        pred = model.predict(X_va_n.fillna(0))
        extra = {"n_features": int(X_tr_n.shape[1]), "_model": model, "variant": "regressor"}
        return pack_metrics(model=model_name, y_va=y_va, pred=np.asarray(pred, dtype=float), meta_va=meta_va, extra=extra)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "License" in type(e).__name__ or "TABPFN_TOKEN" in msg or "license" in msg.lower():
            return {
                "model": model_name,
                "status": "skipped",
                "reason": "TabPFN license/token required (set TABPFN_TOKEN); skipped",
            }
        try:
            from tabpfn import TabPFNClassifier
        except ImportError as e2:
            return {"model": model_name, "status": "skipped", "reason": f"tabpfn unavailable: {type(e).__name__}: {e}; {e2}"}
        try:
            yb = y_binary(meta_tr).fillna(0).astype(int)
            clf = TabPFNClassifier(n_estimators=int(n_estimators), random_state=int(seed))
            clf.fit(X_tr_n.fillna(0), yb)
            p = clf.predict_proba(X_va_n.fillna(0))[:, 1]
            cond = float(y_tr[yb.eq(1)].mean()) if (yb == 1).any() else float(y_tr.mean())
            pred = p * cond
            extra = {
                "n_features": int(X_tr_n.shape[1]),
                "_model": clf,
                "variant": "classifier_conditional_mean",
                "regressor_error": str(e)[:200],
            }
            return pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, extra=extra)
        except Exception as e2:  # noqa: BLE001
            msg2 = str(e2)
            if "License" in type(e2).__name__ or "license" in msg2.lower():
                return {
                    "model": model_name,
                    "status": "skipped",
                    "reason": "TabPFN license/token required (set TABPFN_TOKEN); skipped",
                }
            return {"model": model_name, "status": "skipped", "reason": f"{type(e2).__name__}: {e2}"}
