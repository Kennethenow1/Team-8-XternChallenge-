#!/usr/bin/env python3
"""Small TabICL / TabPFN config search (20–35 configs); kill if near random.

  python scripts/run_tfm_config_search.py [--max-configs 30]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.eval_protocol import KILL_THRESHOLDS, SELECTION_SPLIT, assert_selection_split, classification_metrics
from src.modeling.model_registry import ARTIFACTS_DIR, feature_list_from_X, load_xy, save_run_artifacts
from src.modeling.tournament_registry import append_run, refresh_leaderboard


def _prep_foundation() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    X_tr, y_tr, _ = load_xy("foundation_v1", "train")
    X_va, y_va, meta_va = load_xy("foundation_v1", SELECTION_SPLIT)
    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    for df in (X_tr, X_va):
        for c in df.columns:
            if df[c].dtype == object or str(df[c].dtype).startswith("string"):
                df[c] = df[c].astype("string").fillna("__MISSING__").astype(str)
            else:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return X_tr.loc[mask], y_tr.loc[mask], X_va, y_va, meta_va


def _run_tabicl(X_tr, y_tr, X_va, y_va, params: dict[str, Any]) -> dict[str, Any]:
    try:
        from tabicl import TabICLClassifier
    except ImportError as e:
        return {"status": "skipped", "reason": f"tabicl not installed: {e}"}
    try:
        model = TabICLClassifier(**params)
        model.fit(X_tr, y_tr.astype(int))
        proba = model.predict_proba(X_va)[:, 1]
        m = classification_metrics(y_va.astype(float), proba)
        m.update({"status": "ok", "params": params})
        return m
    except Exception as e:  # noqa: BLE001
        return {"status": "skipped", "reason": str(e), "params": params}


def _run_tabpfn(X_tr, y_tr, X_va, y_va, params: dict[str, Any]) -> dict[str, Any]:
    import os

    if not os.environ.get("TABPFN_TOKEN", "").strip():
        return {"status": "skipped", "reason": "TABPFN_TOKEN not set"}
    try:
        from tabpfn import TabPFNClassifier
    except ImportError as e:
        return {"status": "skipped", "reason": f"tabpfn not installed: {e}"}
    try:
        model = TabPFNClassifier(**params)
        model.fit(X_tr, y_tr.astype(int))
        proba = model.predict_proba(X_va)[:, 1]
        m = classification_metrics(y_va.astype(float), proba)
        m.update({"status": "ok", "params": params})
        return m
    except Exception as e:  # noqa: BLE001
        return {"status": "skipped", "reason": str(e), "params": params}


def _config_grid(max_configs: int) -> list[tuple[str, dict[str, Any]]]:
    tabicl_n = [4, 8, 12, 16]
    tabicl_seeds = [13, 42, 73]
    tabpfn_n = [4, 8, 12]
    tabpfn_seeds = [13, 42, 73, 101]

    configs: list[tuple[str, dict[str, Any]]] = []
    for n, seed in itertools.islice(itertools.product(tabicl_n, tabicl_seeds), max_configs // 2 + 5):
        configs.append(("tabicl", {"n_estimators": n, "random_state": seed}))
    for n, seed in itertools.islice(itertools.product(tabpfn_n, tabpfn_seeds), max_configs // 2 + 5):
        configs.append(("tabpfn", {"n_estimators": n, "random_state": seed}))
    return configs[:max_configs]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-configs", type=int, default=30)
    args = parser.parse_args()
    assert_selection_split(SELECTION_SPLIT)

    X_tr, y_tr, X_va, y_va, meta_va = _prep_foundation()
    configs = _config_grid(args.max_configs)
    results: list[dict[str, Any]] = []
    killed = 0

    for i, (family, params) in enumerate(configs):
        print(f"[tfm] {i+1}/{len(configs)} {family} {params}", flush=True)
        if family == "tabicl":
            m = _run_tabicl(X_tr, y_tr, X_va, y_va, params)
        else:
            m = _run_tabpfn(X_tr, y_tr, X_va, y_va, params)

        run_id = f"tfm_{family}_{i}"
        rec = {
            "run_id": run_id,
            "family": family,
            "model": f"{family}_cfg_{i}",
            "status": m.get("status"),
            "reason": m.get("reason"),
            "source": "tfm_config_search",
            "split": "val",
            "test_sealed": True,
            "config": params,
            "pr_auc": m.get("pr_auc"),
            "roc_auc": m.get("roc_auc"),
            "brier": m.get("brier"),
            "log_loss": m.get("log_loss"),
        }
        results.append(rec)
        append_run(rec)

        if m.get("status") == "ok":
            pr = float(m.get("pr_auc") or 0)
            roc = float(m.get("roc_auc") or 0)
            if pr < KILL_THRESHOLDS["pr_auc"] and roc < KILL_THRESHOLDS["roc_auc"]:
                killed += 1
                print(f"  kill_near_random pr={pr:.4f} roc={roc:.4f}", flush=True)
            else:
                print(f"  ok pr={pr:.4f}", flush=True)
        else:
            print(f"  skipped: {m.get('reason')}", flush=True)

    best = max((r for r in results if r.get("pr_auc") is not None), key=lambda r: r["pr_auc"], default=None)
    if best and best.get("status") == "ok":
        name = best["model"]
        if best["family"] == "tabicl":
            from tabicl import TabICLClassifier

            model = TabICLClassifier(**best["config"])
            model.fit(X_tr, y_tr.astype(int))
            proba = model.predict_proba(X_va)[:, 1]
        else:
            from tabpfn import TabPFNClassifier

            model = TabPFNClassifier(**best["config"])
            model.fit(X_tr, y_tr.astype(int))
            proba = model.predict_proba(X_va)[:, 1]
        preds = meta_va.copy()
        preds["y_true"] = y_va.to_numpy()
        preds["y_prob"] = proba
        save_run_artifacts(
            name,
            hyperparams=best["config"],
            feature_list=feature_list_from_X(X_tr),
            train_metadata={"matrix": "foundation_v1", "source": "tfm_config_search"},
            metrics={k: best.get(k) for k in ("pr_auc", "roc_auc", "brier", "log_loss", "status")},
            val_predictions=preds,
            model_obj=model,
        )

    out = ARTIFACTS_DIR / "metrics" / "tfm_config_search.json"
    out.write_text(json.dumps({"results": results, "killed_near_random": killed}, indent=2, default=str), encoding="utf-8")
    refresh_leaderboard()
    print(json.dumps({"n_configs": len(configs), "killed": killed, "best": best}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
