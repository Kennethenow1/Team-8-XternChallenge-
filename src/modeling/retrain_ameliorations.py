#!/usr/bin/env python3
"""Val-only retrain ameliorations. Test sealed. No PCA on trees. No 50/50 rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, QUALITY_DIR
from src.modeling.eval_protocol import STRONG_GOALS, full_eval_metrics, meets_goals
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.model_registry import load_capacity_mw, load_xy
from src.modeling.train_catboost import CATBOOST_TRIAL_149, fit_catboost_eval
from src.modeling.train_lightgbm import fit_lightgbm_eval
from src.modeling.train_logistic import fit_logistic_eval
from src.modeling.train_xgboost import fit_xgboost_eval

REPORT_DIR = QUALITY_DIR / "modeling"
METRICS_DIR = GOLD_DIR / "modeling" / "artifacts" / "metrics"
PANEL_PATH = GOLD_DIR / "withdrawal_panel_enriched.parquet"

SEEDS = (42, 123, 2026)

SPARSE_CANDIDATES = [
    "years_since_last_change",
    "years_since_last_change_missing",
    "capacity_reduction_pct",
    "cost_change_since_previous_study",
    "upgrade_cost_per_mw",
    "study_delay_days",
    "network_upgrade_cost",
]

NEWS_DRIFT_COLS = [
    "news_count_30d",
    "news_count_90d",
    "news_sentiment_mean_90d",
    "negative_news_count_90d",
    "news_recent_intensity",
    "negative_news_share_90d",
]

MONO_UP = [
    "upgrade_cost_per_mw",
    "queue_age_months",
    "developer_prior_withdrawal_rate",
    "years_in_queue",
    "study_delay_days",
]

LGBM_LOGLOSS_FOCUS: dict[str, Any] = {
    "learning_rate": 0.02,
    "num_leaves": 16,
    "max_depth": 4,
    "min_child_samples": 80,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.5,
    "reg_lambda": 5.0,
    "n_estimators": 5000,
    "early_stopping_rounds": 100,
    "random_state": 2026,
}

XGB_LOGLOSS_FOCUS: dict[str, Any] = {
    "learning_rate": 0.02,
    "max_depth": 3,
    "min_child_weight": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.5,
    "reg_lambda": 5.0,
    "gamma": 0.5,
    "n_estimators": 5000,
    "early_stopping_rounds": 100,
    "random_state": 2026,
}

METRIC_KEYS = (
    "pr_auc",
    "pr_lift",
    "roc_auc",
    "log_loss",
    "brier",
    "ece",
    "precision_at_10pct",
    "recall_at_10pct",
    "withdrawn_mw_capture_at_10pct",
    "positive_rate",
    "n_features",
    "best_iteration",
    "status",
    "reason",
    "dump",
    "dump_reason",
    "flag_rate_at_0_5",
    "mean_y_prob",
)


def _public(metrics: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in metrics.items():
        if str(k).startswith("_"):
            continue
        if k == "history":
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v) if np.isfinite(v) else None
        elif isinstance(v, (float, int, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)) and len(v) <= 200:
            out[k] = list(v)
        else:
            try:
                json.dumps(v)
                out[k] = v
            except TypeError:
                out[k] = str(v)
    return out


def _flag_cries_wolf(metrics: dict[str, Any]) -> dict[str, Any]:
    """Dump a reweight/focal run that only flags everyone."""
    proba = metrics.get("_proba")
    y = metrics.get("_y_va")
    prev = float(metrics.get("positive_rate") or metrics.get("val_prevalence") or 0.041)
    dump = False
    reasons: list[str] = []
    flag_rate = float("nan")
    mean_p = float("nan")
    if proba is not None:
        p = np.asarray(proba, dtype=float)
        mean_p = float(np.nanmean(p))
        flag_rate = float(np.mean(p >= 0.5))
        metrics["flag_rate_at_0_5"] = flag_rate
        metrics["mean_y_prob"] = mean_p
        if flag_rate > 0.35:
            dump = True
            reasons.append(f"flag_rate@0.5={flag_rate:.3f} (>0.35)")
        if mean_p > max(0.20, 4 * prev):
            dump = True
            reasons.append(f"mean_y_prob={mean_p:.3f} vs prevalence={prev:.3f}")
    ll = metrics.get("log_loss")
    if ll is not None and np.isfinite(float(ll)) and float(ll) > 0.25:
        dump = True
        reasons.append(f"log_loss={float(ll):.3f} (>0.25 — over-calling risk)")
    prec = metrics.get("precision_at_10pct")
    rec = metrics.get("recall_at_10pct")
    if prec is not None and rec is not None and np.isfinite(float(prec)) and np.isfinite(float(rec)):
        if float(prec) <= prev * 1.15 and float(rec) >= 0.80:
            dump = True
            reasons.append("high recall@10% with chance-level precision")
    metrics["dump"] = dump
    metrics["dump_reason"] = "; ".join(reasons) if reasons else ""
    return metrics


def _cpu_trial149(seed: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    p = {**CATBOOST_TRIAL_149, "random_seed": int(seed), "task_type": "CPU"}
    p.pop("devices", None)
    if extra:
        p.update(extra)
    return p


def _fit_cb(*, name: str, seed: int = 2026, extra_params: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    print(f"=== {name} ===", flush=True)
    params = _cpu_trial149(seed, extra_params)
    out = fit_catboost_eval(params=params, model_name=name, save=False, **kwargs)
    if out.get("status") != "ok" and "skipped" not in str(out.get("status", "ok")):
        out.setdefault("status", "ok")
    if "_proba" in out:
        _flag_cries_wolf(out)
    print(
        f"    pr_auc={out.get('pr_auc')} roc={out.get('roc_auc')} "
        f"logloss={out.get('log_loss')} mw10={out.get('withdrawn_mw_capture_at_10pct')}",
        flush=True,
    )
    return out


def shap_mean_abs(model: Any, X_va: pd.DataFrame, y_va: pd.Series, cat_cols: list[str]) -> pd.Series:
    from catboost import EFstrType, Pool

    pool = Pool(X_va, y_va.astype(int), cat_features=[c for c in cat_cols if c in X_va.columns])
    shap = np.asarray(model.get_feature_importance(data=pool, type=EFstrType.ShapValues))
    core = shap[:, :-1] if shap.ndim == 2 and shap.shape[1] == X_va.shape[1] + 1 else shap
    return pd.Series(np.abs(core).mean(axis=0), index=list(X_va.columns))


def permutation_mean(model: Any, X_va: pd.DataFrame, y_va: pd.Series, *, n: int = 400) -> pd.Series:
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import average_precision_score

    rng = np.random.default_rng(2026)
    idx = np.arange(len(X_va))
    if len(idx) > n:
        idx = rng.choice(idx, size=n, replace=False)
    Xs = X_va.iloc[idx]
    ys = y_va.iloc[idx].astype(int)

    def _scorer(est, X, y):
        p = est.predict_proba(X)[:, 1]
        return float(average_precision_score(y, p))

    r = permutation_importance(model, Xs, ys, scoring=_scorer, n_repeats=3, random_state=2026, n_jobs=1)
    return pd.Series(r.importances_mean, index=list(X_va.columns))


def bottom_frac_drop(importance: pd.Series, X: pd.DataFrame, *, frac: float = 0.20) -> list[str]:
    keep_cats = [c for c in NATIVE_CATEGORICALS if c in X.columns]
    ranked = importance.drop(labels=[c for c in keep_cats if c in importance.index], errors="ignore")
    n_drop = max(1, int(np.floor(len(ranked) * frac)))
    return [c for c in ranked.nsmallest(n_drop).index.tolist() if c in X.columns]


def join_panel_flags(meta: pd.DataFrame) -> pd.DataFrame:
    need = ["project_key", "observation_date", "never_in_training", "developer_id", "split"]
    probe = pd.read_parquet(PANEL_PATH)
    cols = [c for c in need if c in probe.columns]
    panel = probe[cols].copy()
    panel["observation_date"] = pd.to_datetime(panel["observation_date"])
    left = meta.copy()
    left["observation_date"] = pd.to_datetime(left["observation_date"])
    return left.merge(panel, on=["project_key", "observation_date"], how="left", suffixes=("", "_panel"))


def slice_metrics(
    y: pd.Series,
    proba: np.ndarray,
    capacity: pd.Series,
    mask: pd.Series,
    *,
    name: str,
) -> dict[str, Any]:
    m = mask.fillna(False).astype(bool).to_numpy()
    if m.sum() < 20 or pd.Series(y).to_numpy()[m].sum() < 2:
        return {"slice": name, "status": "skipped", "reason": "too few positives", "n": int(m.sum())}
    out = full_eval_metrics(pd.Series(y).to_numpy()[m], np.asarray(proba)[m], pd.Series(capacity).to_numpy()[m])
    out["slice"] = name
    out["status"] = "ok"
    out["n"] = int(m.sum())
    return out


def cold_start_report(run: dict[str, Any]) -> list[dict[str, Any]]:
    meta = run["_meta_va"]
    y = run["_y_va"]
    proba = run["_proba"]
    cap = run["_capacity"]
    joined = join_panel_flags(meta)
    rows = []
    if "never_in_training" in joined.columns:
        flag = joined["never_in_training"]
        if flag.dtype == object:
            flag = flag.astype("string").str.lower().isin(["true", "1", "yes"])
        else:
            flag = flag.astype(bool)
        rows.append(slice_metrics(y, proba, cap, flag, name="never_in_training"))
        rows.append(slice_metrics(y, proba, cap, ~flag, name="seen_in_training"))
    if "developer_id" in joined.columns:
        train_panel = pd.read_parquet(PANEL_PATH)
        if "split" in train_panel.columns:
            seen_dev = set(train_panel.loc[train_panel["split"] == "train", "developer_id"].dropna().astype(str))
        else:
            year = pd.to_datetime(train_panel["observation_date"]).dt.year
            seen_dev = set(train_panel.loc[year.between(2020, 2022), "developer_id"].dropna().astype(str))
        is_new = ~joined["developer_id"].astype("string").isin(seen_dev)
        rows.append(slice_metrics(y, proba, cap, is_new, name="new_developer"))
        rows.append(slice_metrics(y, proba, cap, ~is_new, name="seen_developer"))
    return rows


def fit_logistic_rotation(*, mode: str, n_pls: int = 8) -> dict[str, Any]:
    """current vs train-only PLS vs PCA-90% negative control on logistic numerics."""
    from sklearn.cross_decomposition import PLSRegression
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression

    print(f"=== logistic_{mode} ===", flush=True)
    X_tr, y_tr, _ = load_xy("logistic_v1", "train")
    X_va, y_va, meta_va = load_xy("logistic_v1", "val")
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
    capacity = load_capacity_mw(meta_va)

    dummy_or_flag = [c for c in X_tr.columns if "__" in c or str(c).endswith("_missing")]
    num_cols = [c for c in X_tr.columns if c not in dummy_or_flag]
    rest_cols = [c for c in dummy_or_flag if c in X_tr.columns]

    if mode == "current":
        Z_tr = X_tr.to_numpy(dtype=float)
        Z_va = X_va.to_numpy(dtype=float)
        extra: dict[str, Any] = {"rotation": "none"}
    else:
        Xt = X_tr[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        Xv = X_va[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        Rt = X_tr[rest_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float) if rest_cols else None
        Rv = X_va[rest_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float) if rest_cols else None
        if mode == "pls":
            n_comp = int(min(n_pls, Xt.shape[1], max(Xt.shape[0] - 1, 1)))
            rot = PLSRegression(n_components=n_comp, scale=False)
            rot.fit(Xt, y_tr.astype(float))
            T_tr = np.asarray(rot.transform(Xt))
            T_va = np.asarray(rot.transform(Xv))
            extra = {"rotation": "pls", "n_components": n_comp, "numeric_cols": num_cols}
        elif mode == "pca":
            rot = PCA(n_components=0.90, svd_solver="full", random_state=42)
            T_tr = rot.fit_transform(Xt)
            T_va = rot.transform(Xv)
            extra = {
                "rotation": "pca_90pct_negative_control",
                "n_components": int(getattr(rot, "n_components_", T_tr.shape[1])),
                "explained_variance_ratio_sum": float(np.sum(rot.explained_variance_ratio_)),
            }
        else:
            raise ValueError(mode)
        Z_tr = np.hstack([T_tr, Rt]) if Rt is not None and Rt.size else T_tr
        Z_va = np.hstack([T_va, Rv]) if Rv is not None and Rv.size else T_va

    clf = LogisticRegression(solver="saga", C=1.0, max_iter=10_000, l1_ratio=0.0, random_state=42)
    clf.fit(Z_tr, y_tr.astype(int))
    proba = clf.predict_proba(Z_va)[:, 1]
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update({"status": "ok", "model": f"logistic_{mode}", "split": "val", **extra})
    print(f"    pr_auc={metrics.get('pr_auc')} logloss={metrics.get('log_loss')}", flush=True)
    return metrics


def _leaderboard_row(metrics: dict[str, Any]) -> dict[str, Any]:
    row = {"model": metrics.get("model")}
    for k in METRIC_KEYS:
        if k in metrics:
            v = metrics[k]
            if isinstance(v, (np.floating, np.integer)):
                row[k] = float(v)
            else:
                row[k] = v
    row["strong"] = bool(metrics.get("status") == "ok" and meets_goals(metrics, STRONG_GOALS))
    return row


def _md_table(rows: list[dict[str, Any]], cols: list[str]) -> list[str]:
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                cells.append(f"{v:.4f}" if np.isfinite(v) else "")
            elif v is None:
                cells.append("")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def run_retrain_ameliorations() -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    notes: list[str] = []

    ref = _fit_cb(name="catboost_unweighted_seed2026", seed=2026)
    runs.append(ref)
    if ref.get("status") != "ok" and not ref.get("pr_auc"):
        notes.append(f"reference CatBoost failed: {ref.get('reason')}")

    seed_probas: list[np.ndarray] = []
    seed_meta = None
    for seed in SEEDS:
        if seed == 2026 and ref.get("_proba") is not None:
            r = ref
        else:
            r = _fit_cb(name=f"catboost_trial149_seed{seed}", seed=seed)
            runs.append(r)
        if r.get("_proba") is not None:
            seed_probas.append(np.asarray(r["_proba"], dtype=float))
            seed_meta = r

    if seed_probas and seed_meta is not None:
        bag = np.mean(np.vstack(seed_probas), axis=0)
        bag_m = full_eval_metrics(seed_meta["_y_va"].astype(float), bag, seed_meta["_capacity"])
        bag_m.update({"status": "ok", "model": "catboost_seed_bag_42_123_2026", "split": "val"})
        print(
            f"=== catboost_seed_bag === pr_auc={bag_m.get('pr_auc')} "
            f"mw10={bag_m.get('withdrawn_mw_capture_at_10pct')}",
            flush=True,
        )
        runs.append(bag_m)

    # SHAP / permutation trim on the seed-2026 model
    if ref.get("_model") is not None and ref.get("_X_va") is not None:
        model = ref["_model"]
        X_va = ref["_X_va"]
        y_va = ref["_y_va"]
        cat_cols = ref.get("_cat_cols") or [c for c in NATIVE_CATEGORICALS if c in X_va.columns]
        try:
            shap_imp = shap_mean_abs(model, X_va, y_va, cat_cols)
            shap_drop = bottom_frac_drop(shap_imp, ref.get("_X_tr", X_va), frac=0.20)
            shap_path = METRICS_DIR / "retrain_catboost_shap_importance.csv"
            shap_imp.sort_values(ascending=False).rename("mean_abs_shap").to_csv(shap_path, header=True)
            notes.append(f"SHAP drop {len(shap_drop)} cols (bottom 20%, cats kept): {shap_drop[:12]}")
            shap_run = _fit_cb(name="catboost_shap_trim", seed=2026, drop_cols=shap_drop)
            shap_run["dropped_features"] = shap_drop
            runs.append(shap_run)
        except Exception as e:  # noqa: BLE001
            notes.append(f"SHAP trim skipped: {type(e).__name__}: {e}")
            runs.append({"model": "catboost_shap_trim", "status": "skipped", "reason": str(e)})
        try:
            perm_imp = permutation_mean(model, X_va, y_va)
            perm_drop = bottom_frac_drop(perm_imp, ref.get("_X_tr", X_va), frac=0.20)
            perm_path = METRICS_DIR / "retrain_catboost_permutation_importance.csv"
            perm_imp.sort_values(ascending=False).rename("perm_pr_auc_drop").to_csv(perm_path, header=True)
            notes.append(f"Permutation drop {len(perm_drop)} cols: {perm_drop[:12]}")
            perm_run = _fit_cb(name="catboost_perm_trim", seed=2026, drop_cols=perm_drop)
            perm_run["dropped_features"] = perm_drop
            runs.append(perm_run)
        except Exception as e:  # noqa: BLE001
            notes.append(f"Permutation trim skipped: {type(e).__name__}: {e}")
            runs.append({"model": "catboost_perm_trim", "status": "skipped", "reason": str(e)})

    runs.append(_fit_cb(name="catboost_mw_sample_weight", seed=2026, sample_weight_from="capacity_mw"))

    X_tr_cb, _, _ = load_xy("catboost_native_v1", "train")
    sparse_present = [c for c in SPARSE_CANDIDATES if c in X_tr_cb.columns]
    missing = [c for c in SPARSE_CANDIDATES if c not in X_tr_cb.columns]
    notes.append(
        "Sparse already absent from catboost_native_v1 (V1 HARD_DROPS / not in matrix): "
        + (", ".join(missing) if missing else "none")
    )
    if sparse_present:
        sparse_run = _fit_cb(name="catboost_drop_sparse", seed=2026, drop_cols=sparse_present)
        sparse_run["dropped_features"] = sparse_present
        runs.append(sparse_run)
    else:
        runs.append(
            {
                "model": "catboost_drop_sparse",
                "status": "skipped",
                "reason": "no sparse candidates remain on catboost_native_v1 (years_since_last_change already hard-dropped)",
            }
        )

    news_present = [c for c in NEWS_DRIFT_COLS if c in X_tr_cb.columns]
    notes.append("Drift ablation drops news* only; macros kept (prior minus-macro ablation hurt).")
    if news_present:
        drift_run = _fit_cb(name="catboost_drop_news_drift", seed=2026, drop_cols=news_present)
        drift_run["dropped_features"] = news_present
        runs.append(drift_run)
    else:
        runs.append({"model": "catboost_drop_news_drift", "status": "skipped", "reason": "no news columns on matrix"})

    mono = {c: 1 for c in MONO_UP if c in X_tr_cb.columns}
    if mono:
        runs.append(_fit_cb(name="catboost_monotone", seed=2026, monotone_constraints=mono))
    else:
        runs.append({"model": "catboost_monotone", "status": "skipped", "reason": "no monotone columns present"})

    runs.append(
        _fit_cb(
            name="catboost_auto_class_weights",
            seed=2026,
            extra_params={"auto_class_weights": "Balanced"},
        )
    )
    try:
        runs.append(
            _fit_cb(
                name="catboost_focal",
                seed=2026,
                extra_params={"loss_function": "Focal:focal_alpha=0.25;focal_gamma=2.0", "eval_metric": "Logloss"},
            )
        )
    except Exception as e:  # noqa: BLE001
        runs.append({"model": "catboost_focal", "status": "skipped", "reason": str(e)})

    cold = []
    if ref.get("_proba") is not None:
        try:
            cold = cold_start_report(ref)
        except Exception as e:  # noqa: BLE001
            notes.append(f"cold-start skipped: {e}")
            cold = [{"slice": "cold_start", "status": "skipped", "reason": str(e)}]

    print("=== lightgbm_default ===", flush=True)
    lgbm_def = fit_lightgbm_eval(model_name="lightgbm_default", save=False)
    runs.append(lgbm_def)
    print("=== lightgbm_logloss_focus ===", flush=True)
    lgbm_ll = fit_lightgbm_eval(params=LGBM_LOGLOSS_FOCUS, model_name="lightgbm_logloss_focus", save=False)
    runs.append(lgbm_ll)
    print("=== xgboost_default ===", flush=True)
    xgb_def = fit_xgboost_eval(model_name="xgboost_default", save=False)
    runs.append(xgb_def)
    print("=== xgboost_logloss_focus ===", flush=True)
    xgb_ll = fit_xgboost_eval(params=XGB_LOGLOSS_FOCUS, model_name="xgboost_logloss_focus", save=False)
    runs.append(xgb_ll)

    for mode in ("current", "pls", "pca"):
        try:
            runs.append(fit_logistic_rotation(mode=mode))
        except Exception as e:  # noqa: BLE001
            runs.append({"model": f"logistic_{mode}", "status": "skipped", "reason": str(e)})

    notes.append("TabM PLS is low-priority; use electrum/05_tabm.ipynb (USE_PLS knob) rather than this batch.")

    public_runs = [_public(r) for r in runs]
    lb = [_leaderboard_row(r) for r in public_runs]
    ref_pr = float(ref.get("pr_auc") or float("nan"))
    promote: list[str] = []
    for r in public_runs:
        if r.get("model") == "catboost_unweighted_seed2026":
            continue
        if str(r.get("model", "")).startswith("catboost_trial149_seed"):
            # Same trial-149 recipe, different seed — seed stability, not a new method.
            continue
        if r.get("status") == "ok" and meets_goals(r, STRONG_GOALS):
            pr = r.get("pr_auc")
            if pr is not None and np.isfinite(float(pr)) and float(pr) > ref_pr + 1e-4:
                promote.append(str(r.get("model")))

    payload = {
        "test_sealed": True,
        "split": "val",
        "reference": "catboost_unweighted_seed2026",
        "reference_pr_auc": ref.get("pr_auc"),
        "promote_candidates": promote,
        "promote": False,
        "promote_note": (
            "Promote only if a variant beats unrotated CatBoost tuned on Strong gates. "
            "None did." if not promote else
            "Val-only candidates that beat the unrotated seed-2026 reference on Strong + PR-AUC. "
            "Do not unseal test."
        ),
        "notes": notes,
        "cold_start": cold,
        "runs": public_runs,
    }
    if promote:
        payload["promote"] = False  # still do not change deploy without freeze re-approval
        payload["promote_note"] = (
            "These variants beat the unrotated reference on val Strong + PR-AUC, but deploy "
            "stays catboost_tuned + Platt until freeze is re-approved. Test remains sealed. "
            f"Candidates: {promote}"
        )

    (METRICS_DIR / "retrain_ameliorations.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(lb).to_csv(METRICS_DIR / "retrain_ameliorations.csv", index=False)
    if cold:
        pd.DataFrame([{k: v for k, v in c.items() if not str(k).startswith("_")} for c in cold]).to_csv(
            METRICS_DIR / "retrain_cold_start.csv", index=False
        )

    cols = [
        "model",
        "status",
        "pr_auc",
        "pr_lift",
        "roc_auc",
        "log_loss",
        "withdrawn_mw_capture_at_10pct",
        "precision_at_10pct",
        "strong",
        "dump",
    ]
    lines = [
        "# Retrain val comparison",
        "",
        "Selection on **val 2023** only. Test sealed. No PCA on trees. No split shuffle. No 50/50 resampling.",
        "",
        f"Reference: `{payload['reference']}` PR-AUC = `{payload.get('reference_pr_auc')}`.",
        "",
        payload["promote_note"],
        "",
        "## Leaderboard",
        "",
        *_md_table(lb, cols),
        "",
        "## Strong gates",
        "",
        "PR-AUC ≥ 0.10, PR-lift ≥ 2.5, ROC ≥ 0.74, log-loss ≤ 0.195, MW@10% ≥ 0.22.",
        "",
        "## Notes",
        "",
    ]
    for n in notes:
        lines.append(f"- {n}")
    if cold:
        lines.extend(["", "## Cold-start slices (seed-2026 CatBoost)", ""])
        cold_rows = []
        for c in cold:
            cold_rows.append(
                {
                    "slice": c.get("slice"),
                    "status": c.get("status"),
                    "n": c.get("n"),
                    "pr_auc": c.get("pr_auc"),
                    "log_loss": c.get("log_loss"),
                    "withdrawn_mw_capture_at_10pct": c.get("withdrawn_mw_capture_at_10pct"),
                    "reason": c.get("reason", ""),
                }
            )
        lines.extend(
            _md_table(
                cold_rows,
                ["slice", "status", "n", "pr_auc", "log_loss", "withdrawn_mw_capture_at_10pct", "reason"],
            )
        )
    lines.extend(
        [
            "",
            "## Locked rules",
            "",
            "See [`retrain_notes.md`](retrain_notes.md).",
            "",
        ]
    )
    (REPORT_DIR / "retrain_val_compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"n_runs": len(runs), "promote_candidates": promote}, indent=2), flush=True)
    return payload
