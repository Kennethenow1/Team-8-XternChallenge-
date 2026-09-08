#!/usr/bin/env python3
"""CatBoost V1 vs V1−Macro ablation; record HPO feature-set choice.

  python scripts/run_catboost_macro_ablation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.feature_policy import MACRO_FAMILY
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs
from src.modeling.train_catboost import fit_catboost_eval, train_catboost_v1_minus_macro


METRIC_KEYS = [
    "pr_auc",
    "roc_auc",
    "brier",
    "ece",
    "log_loss",
    "precision_at_5pct",
    "precision_at_10pct",
    "recall_at_10pct",
    "lift_at_10pct",
    "withdrawn_mw_capture_at_10pct",
    "best_iteration",
    "n_features",
]


def _pick_winner(v1: dict, v1m: dict) -> str:
    """Prefer higher PR-AUC; tie-break lower LogLoss then lower Brier."""
    a, b = float(v1["pr_auc"]), float(v1m["pr_auc"])
    if abs(a - b) > 1e-6:
        return "v1" if a > b else "v1_minus_macro"
    la, lb = float(v1["log_loss"]), float(v1m["log_loss"])
    if abs(la - lb) > 1e-6:
        return "v1" if la < lb else "v1_minus_macro"
    ba, bb = float(v1["brier"]), float(v1m["brier"])
    return "v1" if ba <= bb else "v1_minus_macro"


def main() -> int:
    ensure_artifact_dirs()
    metrics_dir = ARTIFACTS_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    print("=== catboost V1 ===", flush=True)
    v1 = fit_catboost_eval(model_name="catboost", save=True)
    print("=== catboost V1−Macro ===", flush=True)
    v1m = train_catboost_v1_minus_macro()

    winner = _pick_winner(v1, v1m)
    choice = {
        "feature_set": winner,
        "drop_cols": list(MACRO_FAMILY) if winner == "v1_minus_macro" else [],
        "macro_family": list(MACRO_FAMILY),
        "selection_rule": "max val PR-AUC; tie-break lower LogLoss then lower Brier",
        "v1": {k: v1.get(k) for k in METRIC_KEYS},
        "v1_minus_macro": {k: v1m.get(k) for k in METRIC_KEYS},
        "test_sealed": True,
    }
    (metrics_dir / "catboost_hpo_feature_set.json").write_text(
        json.dumps(choice, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# CatBoost V1 vs V1−Macro",
        "",
        "Same default CatBoost settings; early stop on val LogLoss.",
        f"Macros dropped in V1−Macro ({len(MACRO_FAMILY)}): `" + "`, `".join(MACRO_FAMILY) + "`.",
        "",
        f"**HPO feature set:** `{winner}`",
        "",
        "| metric | V1 | V1−Macro |",
        "|--------|----|----------|",
    ]
    for k in METRIC_KEYS:
        lines.append(f"| `{k}` | {v1.get(k)} | {v1m.get(k)} |")
    lines.extend(
        [
            "",
            f"Choice artifact: `{metrics_dir / 'catboost_hpo_feature_set.json'}`",
            "",
        ]
    )
    md = metrics_dir / "catboost_v1_vs_v1_macro.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"winner": winner, "md": str(md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
