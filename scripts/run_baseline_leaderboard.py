#!/usr/bin/env python3
"""Run default baselines and write validation leaderboard (test sealed).

  python scripts/run_baseline_leaderboard.py
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.eval_protocol import split_sanity_baselines, write_leaderboard
from src.modeling.model_registry import ensure_artifact_dirs, load_xy
from src.modeling.train_catboost import train_catboost_default
from src.modeling.train_logistic import (
    train_constant_baseline,
    train_logistic_elasticnet_default,
    train_logistic_l2_default,
)
from src.modeling.train_tabicl import train_tabicl_default
from src.modeling.train_tabm import train_tabm_default
from src.modeling.train_tabpfn import train_tabpfn_default
from src.modeling.train_xgboost import train_xgboost_default


def _row_from_metrics(m: dict) -> dict:
    return {
        "model": m.get("model"),
        "status": m.get("status", "ok"),
        "pr_auc": m.get("pr_auc"),
        "roc_auc": m.get("roc_auc"),
        "brier": m.get("brier"),
        "ece": m.get("ece"),
        "log_loss": m.get("log_loss"),
        "n": m.get("n"),
        "reason": m.get("reason", ""),
    }


def main() -> int:
    ensure_artifact_dirs()
    _, y_tr, _ = load_xy("logistic_v1", "train")
    _, y_va, _ = load_xy("logistic_v1", "val")
    prev_train = float(y_tr.dropna().mean())
    prev_val = float(y_va.dropna().mean())

    runners = [
        ("constant", train_constant_baseline),
        ("logistic_l2", train_logistic_l2_default),
        ("logistic_elasticnet", train_logistic_elasticnet_default),
        ("catboost", train_catboost_default),
        ("xgboost", train_xgboost_default),
        ("tabicl", train_tabicl_default),
        ("tabpfn", train_tabpfn_default),
        ("tabm", train_tabm_default),
    ]

    rows = []
    for name, fn in runners:
        print(f"=== {name} ===", flush=True)
        try:
            m = fn()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            m = {"model": name, "status": "skipped", "reason": str(e)}
        print(json.dumps({k: m.get(k) for k in ("model", "status", "pr_auc", "brier", "reason")}, default=str))
        rows.append(_row_from_metrics(m))

    paths = write_leaderboard(
        rows,
        stem="val_baseline_leaderboard",
        train_prevalence=prev_train,
        val_prevalence=prev_val,
    )
    summary = {
        "selection_split": "val",
        "test_sealed": True,
        "sanity_baselines": split_sanity_baselines(prev_train, prev_val),
        "leaderboard_csv": str(paths["csv"]),
        "leaderboard_md": str(paths["md"]),
        "rows": rows,
    }
    out = paths["csv"].parent / "val_baseline_leaderboard_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("Wrote", paths["csv"])
    print("Wrote", paths["md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
