#!/usr/bin/env python3
"""Wire PIT-safe system forecasts into CatBoost V1 (VAL-only ablation).

  python scripts/run_timesfm_catboost_wiring.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.eval_protocol import assert_selection_split
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs
from src.modeling.train_catboost import fit_catboost_eval
from src.modeling.train_timesfm import (
    SYS_FC_PRIMARY_TARGET,
    build_system_forecast_covariates,
)

METRIC_KEYS = [
    "pr_auc",
    "roc_auc",
    "brier",
    "ece",
    "log_loss",
    "precision_at_10pct",
    "recall_at_10pct",
    "lift_at_10pct",
    "withdrawn_mw_capture_at_10pct",
    "best_iteration",
    "n_features",
    "status",
]

# Matched CPU defaults so arm deltas are attributable to sys_fc columns.
CPU_PARAMS: dict[str, Any] = {
    "task_type": "CPU",
}


def _cols_for_engine(fc_columns: list[str], engine: str, *, primary_only: bool = True) -> list[str]:
    suffix = f"_{engine}"
    cols = [c for c in fc_columns if c.endswith(suffix)]
    if primary_only:
        prefix = f"sys_fc_{SYS_FC_PRIMARY_TARGET}_"
        cols = [c for c in cols if c.startswith(prefix)]
    return cols


def _pick_best(arms: dict[str, dict[str, Any]]) -> tuple[str, float]:
    best_name = "catboost_v1"
    best_pr = float(arms[best_name].get("pr_auc") or float("-inf"))
    for name, m in arms.items():
        if m.get("status") != "ok":
            continue
        pr = float(m.get("pr_auc") or float("-inf"))
        if pr > best_pr:
            best_name, best_pr = name, pr
    return best_name, best_pr


def _promotion_verdict(baseline: dict[str, Any], best_name: str, best: dict[str, Any]) -> dict[str, Any]:
    base_pr = float(baseline.get("pr_auc") or 0.0)
    best_pr = float(best.get("pr_auc") or 0.0)
    delta = best_pr - base_pr
    strong = best_pr >= 0.10
    material = delta >= 0.01
    promote = bool(strong and material and best_name != "catboost_v1")
    if promote:
        reason = (
            f"{best_name} beats V1 by {delta:.4f} PR-AUC and meets Strong (pr_auc≥0.10)."
        )
    elif best_name == "catboost_v1":
        reason = "No +sys_fc arm beat matched V1; leave champion freeze unchanged."
    elif not material:
        reason = (
            f"{best_name} delta={delta:.4f} < 0.01 PR-AUC; weak/negative result; "
            "leave champion freeze unchanged."
        )
    else:
        reason = (
            f"{best_name} delta={delta:.4f} but pr_auc={best_pr:.4f} < Strong 0.10; "
            "leave champion freeze unchanged."
        )
    return {
        "promote_interest": promote,
        "best_arm": best_name,
        "baseline_pr_auc": base_pr,
        "best_pr_auc": best_pr,
        "delta_pr_auc": delta,
        "strong": strong,
        "material_lift": material,
        "reason": reason,
        "test_sealed": True,
    }


def main() -> int:
    assert_selection_split("val")
    ensure_artifact_dirs()
    metrics_dir = ARTIFACTS_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    print("=== build PIT-safe system forecast covariates ===", flush=True)
    fc_table, fc_meta = build_system_forecast_covariates(save=True)
    fc_cols = list(fc_meta.get("columns") or [])

    arms: dict[str, dict[str, Any]] = {}

    print("=== catboost_v1 (control, CPU) ===", flush=True)
    arms["catboost_v1"] = fit_catboost_eval(
        model_name="catboost_wiring_v1",
        params=CPU_PARAMS,
        save=True,
    )

    ma3_cols = _cols_for_engine(fc_cols, "ma3", primary_only=True)
    print(f"=== catboost_plus_sys_fc_ma3 cols={ma3_cols} ===", flush=True)
    arms["catboost_plus_sys_fc_ma3"] = fit_catboost_eval(
        model_name="catboost_plus_sys_fc_ma3",
        sys_fc_table=fc_table,
        sys_fc_cols=ma3_cols,
        params=CPU_PARAMS,
        save=True,
    )

    tfm_cols = _cols_for_engine(fc_cols, "timesfm", primary_only=True)
    print(f"=== catboost_plus_sys_fc_timesfm cols={tfm_cols} ===", flush=True)
    arms["catboost_plus_sys_fc_timesfm"] = fit_catboost_eval(
        model_name="catboost_plus_sys_fc_timesfm",
        sys_fc_table=fc_table,
        sys_fc_cols=tfm_cols,
        params=CPU_PARAMS,
        save=True,
    )

    all_primary = [
        c
        for eng in ("naive", "ma3", "timesfm")
        for c in _cols_for_engine(fc_cols, eng, primary_only=True)
    ]
    print(f"=== catboost_plus_sys_fc_all cols={all_primary} ===", flush=True)
    arms["catboost_plus_sys_fc_all"] = fit_catboost_eval(
        model_name="catboost_plus_sys_fc_all",
        sys_fc_table=fc_table,
        sys_fc_cols=all_primary,
        params=CPU_PARAMS,
        save=True,
    )

    slim = {name: {k: m.get(k) for k in METRIC_KEYS} for name, m in arms.items()}
    best_name, _ = _pick_best(arms)
    verdict = _promotion_verdict(arms["catboost_v1"], best_name, arms[best_name])

    payload = {
        "protocol": "train on TRAIN, eval on VAL; TEST sealed",
        "matrix": "catboost_native_v1",
        "task_type": "CPU",
        "forecast_meta": fc_meta,
        "arms": slim,
        "verdict": verdict,
    }
    out_json = metrics_dir / "timesfm_catboost_wiring.json"
    out_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# TimesFM → CatBoost covariate wiring (VAL only)",
        "",
        "PIT-safe year-grain system forecasts joined onto `catboost_native_v1` "
        "(history year < observation year). Matched **CPU** CatBoost defaults "
        "(seed 42, early stop on LogLoss). TEST sealed.",
        "",
        f"Forecast table: `{fc_meta.get('path')}`",
        "",
        "Note: panel grain is annual (~7 snapshots). TimesFM needs ≥3 history "
        "points, so train years 2020–2022 often lack TimesFM values; VAL year "
        "forecasts are constant within-year (system-level signal).",
        "",
        "## VAL metrics",
        "",
        "| Arm | PR-AUC | ROC | LogLoss | MW@10% | n_feat | status |",
        "|-----|--------|-----|---------|--------|--------|--------|",
    ]
    for name, m in arms.items():
        lines.append(
            "| {name} | {pr:.4f} | {roc:.4f} | {ll:.4f} | {mw:.4f} | {nf} | {st} |".format(
                name=name,
                pr=float(m.get("pr_auc") or float("nan")),
                roc=float(m.get("roc_auc") or float("nan")),
                ll=float(m.get("log_loss") or float("nan")),
                mw=float(m.get("withdrawn_mw_capture_at_10pct") or float("nan")),
                nf=m.get("n_features"),
                st=m.get("status"),
            )
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            "**Rule:** promote interest only if `+sys_fc` beats matched V1 by "
            "**≥0.01 PR-AUC** *and* Strong (`pr_auc ≥ 0.10`).",
            "",
            f"**Best arm:** `{verdict['best_arm']}` "
            f"(PR-AUC {verdict['best_pr_auc']:.4f}, "
            f"Δ vs V1 = {verdict['delta_pr_auc']:+.4f})",
            "",
            f"**Verdict:** {verdict['reason']}",
            "",
            f"Promote interest: **{verdict['promote_interest']}**. "
            "Champion freeze / TEST seal unchanged unless promote.",
            "",
        ]
    )
    out_md = metrics_dir / "timesfm_catboost_wiring.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"verdict": verdict, "md": str(out_md)}, indent=2, default=str))
    return 0 if arms["catboost_v1"].get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
