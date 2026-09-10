"""Survival time-to-COD vs withdrawal → implied delay vs cod_at_t."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.common.paths import GOLD_DIR
from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

SURV_PATH = GOLD_DIR / "delay" / "survival_cod_training.parquet"
NUM = [
    "queue_age_months",
    "log1p_capacity_mw",
    "months_until_service",
    "service_date_shift_months",
    "years_in_queue",
    "capacity_mw",
]
CAT = ["technology_primary", "state_code", "study_phase", "service_type"]


def _year_split(start: pd.Series) -> pd.Series:
    year = pd.to_datetime(start).dt.year
    return calendar_like(year)


def calendar_like(year: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(
            year.between(2020, 2022),
            "train",
            np.where(year == 2023, "val", np.where(year == 2024, "test", np.where(year >= 2025, "score", "other"))),
        ),
        index=year.index,
    )


def fit_survival_delay(*, variant: str = "aft_lgbm", model_name: str = "survival") -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    X_va, y_va, meta_va = load_xy("delay_foundation_v1", SELECTION_SPLIT)
    mva = labeled_mask(y_va)
    y_va, meta_va = y_va.loc[mva], meta_va.loc[mva]
    if not SURV_PATH.exists():
        return {"model": model_name, "status": "skipped", "reason": "survival_cod_training.parquet missing"}
    df = pd.read_parquet(SURV_PATH)
    df["split"] = _year_split(df["start_date"])
    nums = [c for c in NUM if c in df.columns]
    X = df[nums].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if any(c in df.columns for c in CAT):
        X = pd.concat(
            [X, pd.get_dummies(df[[c for c in CAT if c in df.columns]].astype("string").fillna("__MISSING__"))],
            axis=1,
        )
    tr = df["split"].eq("train")
    if variant == "discrete_logistic":
        y_ev = (df["operation_event"].fillna(0).astype(int) == 0) & (pd.to_numeric(df.get("service_date_shift_months"), errors="coerce").fillna(0) >= 12)
        # slip-in-interval proxy: operation not yet, past COD shift
        y_slip = (pd.to_numeric(df.get("service_date_shift_months"), errors="coerce").fillna(0) >= 1).astype(int)
        clf = LogisticRegression(solver="saga", max_iter=4000, C=1.0)
        clf.fit(X.loc[tr].fillna(0), y_slip.loc[tr])
        # map onto val rows by project_key
        va = df["split"].eq("val")
        p = clf.predict_proba(X.loc[va].fillna(0))[:, 1]
        pred_map = pd.Series(p, index=df.loc[va, "project_key"].astype(str).to_numpy())
        pred = meta_va["project_key"].astype(str).map(pred_map).fillna(float(y_va.mean())).to_numpy() * 12.0
        extra = {"variant": variant, "_model": clf, "n_features": int(X.shape[1])}
        return pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, extra=extra)

    # AFT / LGBM on log duration to operation among uncensored operate events
    try:
        import lightgbm as lgb
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"lightgbm missing for AFT: {e}"}
    dur = (pd.to_datetime(df["stop_date"]) - pd.to_datetime(df["start_date"])).dt.days / 30.4375
    y_log = np.log1p(dur.clip(lower=0).fillna(0))
    w = df["operation_event"].fillna(0).astype(float)
    model = lgb.LGBMRegressor(objective="mae", n_estimators=400, learning_rate=0.05, random_state=42)
    model.fit(X.loc[tr].fillna(0), y_log.loc[tr], sample_weight=np.clip(w.loc[tr], 0.1, 1.0))
    va = df["split"].eq("val")
    pred_months = np.expm1(model.predict(X.loc[va].fillna(0)))
    # implied remaining delay vs months_until_service
    mus = pd.to_numeric(df.loc[va, "months_until_service"], errors="coerce").fillna(0).to_numpy()
    slip = np.clip(pred_months - mus, -60, 120)
    pred_map = pd.Series(slip, index=df.loc[va, "project_key"].astype(str).to_numpy())
    pred = meta_va["project_key"].astype(str).map(pred_map).fillna(float(y_va.mean())).to_numpy()
    extra = {"variant": variant, "_model": model, "n_features": int(X.shape[1])}
    return pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, extra=extra)
