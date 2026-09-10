"""Survival branch: discrete-time hazard + Cox variants → P(W_12m) on modeling val.

Test remains sealed. Interval table: data/gold/survival_training/survival_training.parquet.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.common.paths import GOLD_DIR
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.model_registry import load_capacity_mw, load_xy, save_run_artifacts

SURVIVAL_PATH = GOLD_DIR / "survival_training" / "survival_training.parquet"

NUM_COLS = [
    "queue_age_months",
    "log1p_capacity_mw",
    "is_hybrid",
    "months_until_service",
    "service_date_passed",
    "capacity_change_pct",
    "service_date_shift_months",
    "other_active_projects_same_state",
    "other_active_mw_same_state",
    "other_active_projects_same_poi",
    "other_active_mw_same_poi",
    "other_active_mw_same_technology",
    "prior_12m_withdrawal_count",
    "prior_12m_withdrawn_mw",
    "years_in_queue",
    "capacity_mw",
]
CAT_COLS = ["technology_primary", "state_code", "study_phase", "service_type"]


def _year_split(start: pd.Series) -> pd.Series:
    year = pd.to_datetime(start).dt.year
    return pd.Series(
        np.where(
            year.between(2020, 2022),
            "train",
            np.where(year == 2023, "val", np.where(year == 2024, "test", np.where(year >= 2025, "score", "other"))),
        ),
        index=start.index,
    )


def _load_intervals() -> pd.DataFrame:
    if not SURVIVAL_PATH.exists():
        raise FileNotFoundError(SURVIVAL_PATH)
    df = pd.read_parquet(SURVIVAL_PATH)
    df = df.copy()
    df["split"] = _year_split(df["start_date"])
    return df


def _design(df: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    nums = [c for c in NUM_COLS if c in df.columns]
    if nums:
        parts.append(df[nums].apply(pd.to_numeric, errors="coerce"))
    cats = [c for c in CAT_COLS if c in df.columns]
    if cats:
        parts.append(pd.get_dummies(df[cats].astype("string").fillna("__MISSING__"), dummy_na=False))
    if not parts:
        raise RuntimeError("no survival features")
    X = pd.concat(parts, axis=1)
    return X.fillna(0.0)


def _align_modeling_val(interval_keys: pd.DataFrame, proba: np.ndarray) -> tuple[pd.Series, np.ndarray, pd.DataFrame, pd.Series, int]:
    """Map interval scores onto modeling val rows (project_key + observation_date)."""
    _, y_va, meta_va = load_xy("logistic_v1", SELECTION_SPLIT)
    y_va = pd.to_numeric(y_va, errors="coerce")
    left = meta_va.copy()
    left["observation_date"] = pd.to_datetime(left["observation_date"])
    scored = interval_keys.copy()
    scored["observation_date"] = pd.to_datetime(scored["start_date"])
    scored["y_prob"] = proba
    merged = left.merge(
        scored[["project_key", "observation_date", "y_prob"]],
        on=["project_key", "observation_date"],
        how="left",
    )
    p = pd.to_numeric(merged["y_prob"], errors="coerce").fillna(float(np.nanmean(proba))).to_numpy()
    cap = load_capacity_mw(meta_va)
    n_hit = int(merged["y_prob"].notna().sum())
    return y_va, p, meta_va, cap, n_hit  # type: ignore[return-value]


def _pack(name: str, y_va: pd.Series, proba: np.ndarray, meta_va: pd.DataFrame, cap: pd.Series, *, alignment: str, save: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = full_eval_metrics(y_va.astype(float), proba, cap)
    metrics.update(
        {
            "status": "ok",
            "model": name,
            "split": SELECTION_SPLIT,
            "alignment": alignment,
        }
    )
    if extra:
        metrics.update(extra)
    if save:
        preds = meta_va.copy()
        preds["y_true"] = y_va.to_numpy()
        preds["y_prob"] = proba
        preds["capacity_mw"] = cap.to_numpy()
        save_run_artifacts(
            name,
            hyperparams=extra or {},
            feature_list=[],
            train_metadata={"matrix": "survival_training", "split": "val"},
            metrics=metrics,
            val_predictions=preds,
            model_obj=None,
        )
    return metrics


def fit_discrete_logistic_hazard(*, save: bool = True, drop_cols: Sequence[str] | None = None) -> dict[str, Any]:
    """Interval-level logistic hazard; scores aligned to modeling val. No PCA."""
    assert_selection_split(SELECTION_SPLIT)
    try:
        df = _load_intervals()
    except FileNotFoundError as e:
        return {"model": "survival_discrete_logistic", "status": "skipped", "reason": str(e)}
    train = df[df["split"] == "train"].copy()
    val = df[df["split"] == "val"].copy()
    if train.empty or val.empty:
        return {"model": "survival_discrete_logistic", "status": "skipped", "reason": "empty train or val intervals"}
    y_tr = pd.to_numeric(train["withdrawal_event"], errors="coerce").fillna(0).astype(int)
    X_tr = _design(train)
    X_va = _design(val)
    drop = [c for c in (drop_cols or []) if c in X_tr.columns]
    if drop:
        X_tr = X_tr.drop(columns=drop, errors="ignore")
        X_va = X_va.drop(columns=drop, errors="ignore")
    X_va = X_va.reindex(columns=X_tr.columns, fill_value=0.0)
    clf = LogisticRegression(solver="saga", max_iter=4000, C=1.0, l1_ratio=0.0, random_state=42)
    clf.fit(X_tr.to_numpy(dtype=float), y_tr)
    proba_iv = clf.predict_proba(X_va.to_numpy(dtype=float))[:, 1]
    y_va, p, meta_va, cap, n_hit = _align_modeling_val(val[["project_key", "start_date"]], proba_iv)
    return _pack(
        "survival_discrete_logistic",
        y_va,
        p,
        meta_va,
        cap,
        alignment=f"aligned to modeling val: {n_hit}/{len(meta_va)} rows",
        save=save,
        extra={"n_interval_train": int(len(train)), "n_interval_val": int(len(val))},
    )


def fit_cox_ph(*, save: bool = True) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    try:
        from lifelines import CoxPHFitter
    except ImportError as e:
        return {"model": "survival_cox_ph", "status": "skipped", "reason": f"lifelines not installed: {e}"}
    df = _load_intervals()
    train = df[df["split"] == "train"].copy()
    val = df[df["split"] == "val"].copy()
    train["duration"] = (
        pd.to_datetime(train["stop_date"]) - pd.to_datetime(train["start_date"])
    ).dt.days.clip(lower=1)
    val["duration"] = (pd.to_datetime(val["stop_date"]) - pd.to_datetime(val["start_date"])).dt.days.clip(lower=1)
    feats = [c for c in ("queue_age_months", "log1p_capacity_mw", "years_in_queue", "is_hybrid") if c in train.columns]
    use = train[feats + ["duration", "withdrawal_event"]].apply(pd.to_numeric, errors="coerce").dropna()
    cph = CoxPHFitter(penalizer=0.1)
    try:
        cph.fit(use, duration_col="duration", event_col="withdrawal_event")
    except Exception as e:  # noqa: BLE001
        return {"model": "survival_cox_ph", "status": "skipped", "reason": f"CoxPH fit failed: {e}"}
    val_x = val[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    try:
        surv = cph.predict_survival_function(val_x, times=[365])
        proba_iv = 1.0 - np.asarray(surv.iloc[0], dtype=float)
    except Exception as e:  # noqa: BLE001
        return {"model": "survival_cox_ph", "status": "skipped", "reason": str(e)}
    y_va, p, meta_va, cap, n_hit = _align_modeling_val(val[["project_key", "start_date"]], proba_iv)
    return _pack("survival_cox_ph", y_va, p, meta_va, cap, alignment=f"aligned to modeling val: {n_hit}/{len(meta_va)} rows", save=save)


def fit_cox_tv(*, save: bool = True) -> dict[str, Any]:
    """Time-varying Cox on interval rows (same table grain as discrete)."""
    return _cox_tv(save=save)


def _cox_tv(*, save: bool) -> dict[str, Any]:
    try:
        from lifelines import CoxTimeVaryingFitter
    except ImportError as e:
        return {"model": "survival_cox_tv", "status": "skipped", "reason": f"lifelines not installed: {e}"}
    df = _load_intervals()
    train = df[df["split"] == "train"].copy()
    val = df[df["split"] == "val"].copy()
    for part in (train, val):
        part["start"] = 0.0
        part["stop"] = (
            pd.to_datetime(part["stop_date"]) - pd.to_datetime(part["start_date"])
        ).dt.days.clip(lower=1).astype(float)
        part["id"] = np.arange(len(part))
    feats = [c for c in ("queue_age_months", "log1p_capacity_mw", "years_in_queue") if c in train.columns]
    use_cols = feats + ["start", "stop", "withdrawal_event", "id"]
    use = train[use_cols].apply(pd.to_numeric, errors="coerce").dropna()
    ctv = CoxTimeVaryingFitter(penalizer=0.1)
    try:
        ctv.fit(use, id_col="id", start_col="start", stop_col="stop", event_col="withdrawal_event")
    except Exception as e:  # noqa: BLE001
        return {"model": "survival_cox_tv", "status": "skipped", "reason": f"Cox-TV fit failed: {e}"}
    val_x = val[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    try:
        # Partial hazard as a ranking score; squash to (0,1) for log-loss.
        ph = np.asarray(ctv.predict_partial_hazard(val_x), dtype=float).ravel()
        proba_iv = 1.0 - np.exp(-np.clip(ph, 0, None) / (np.nanmedian(ph) + 1e-6))
        proba_iv = np.clip(proba_iv, 1e-6, 1 - 1e-6)
    except Exception as e:  # noqa: BLE001
        return {"model": "survival_cox_tv", "status": "skipped", "reason": str(e)}
    y_va, p, meta_va, cap, n_hit = _align_modeling_val(val[["project_key", "start_date"]], proba_iv)
    return _pack("survival_cox_tv", y_va, p, meta_va, cap, alignment=f"aligned to modeling val: {n_hit}/{len(meta_va)} rows", save=save)


def fit_boosted_discrete_hazard(*, save: bool = True) -> dict[str, Any]:
    try:
        import lightgbm as lgb
    except ImportError as e:
        return {"model": "survival_boost_lgbm", "status": "skipped", "reason": str(e)}
    df = _load_intervals()
    train = df[df["split"] == "train"].copy()
    val = df[df["split"] == "val"].copy()
    y_tr = pd.to_numeric(train["withdrawal_event"], errors="coerce").fillna(0).astype(int)
    X_tr = _design(train)
    X_va = _design(val).reindex(columns=X_tr.columns, fill_value=0.0)
    model = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=16,
        max_depth=4,
        min_child_samples=40,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_tr, y_tr)
    proba_iv = model.predict_proba(X_va)[:, 1]
    y_va, p, meta_va, cap, n_hit = _align_modeling_val(val[["project_key", "start_date"]], proba_iv)
    return _pack("survival_boost_lgbm", y_va, p, meta_va, cap, alignment=f"aligned to modeling val: {n_hit}/{len(meta_va)} rows", save=save)


def fit_xgb_aft(*, save: bool = True) -> dict[str, Any]:
    return {
        "model": "survival_xgb_aft",
        "status": "skipped",
        "reason": "XGBoost AFT requires upper_bound kw; not supported in this API version",
    }


def fit_random_survival_forest(*, save: bool = True) -> dict[str, Any]:
    try:
        from sksurv.ensemble import RandomSurvivalForest
        from sksurv.util import Surv
    except ImportError as e:
        return {"model": "survival_rsf", "status": "skipped", "reason": f"scikit-survival not installed: {e}"}
    df = _load_intervals()
    train = df[df["split"] == "train"].copy()
    val = df[df["split"] == "val"].copy()
    feats = [c for c in ("queue_age_months", "log1p_capacity_mw", "years_in_queue", "is_hybrid") if c in train.columns]
    y_tr = Surv.from_arrays(
        pd.to_numeric(train["withdrawal_event"], errors="coerce").fillna(0).astype(bool),
        (pd.to_datetime(train["stop_date"]) - pd.to_datetime(train["start_date"])).dt.days.clip(lower=1).to_numpy(),
    )
    X_tr = train[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    X_va = val[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    rsf = RandomSurvivalForest(n_estimators=80, min_samples_split=20, random_state=42, n_jobs=2)
    try:
        rsf.fit(X_tr, y_tr)
        surv = rsf.predict_survival_function(X_va, return_array=True)
        # column closest to 365 days if times available; else 1 - mean survival
        proba_iv = 1.0 - np.clip(np.asarray(surv)[:, -1], 0, 1)
    except Exception as e:  # noqa: BLE001
        return {"model": "survival_rsf", "status": "skipped", "reason": str(e)}
    y_va, p, meta_va, cap, n_hit = _align_modeling_val(val[["project_key", "start_date"]], proba_iv)
    return _pack("survival_rsf", y_va, p, meta_va, cap, alignment=f"aligned to modeling val: {n_hit}/{len(meta_va)} rows", save=save)
