#!/usr/bin/env python3
"""Top-model feature ablations (CatBoost + LightGBM) on validation only.

  python scripts/run_top_model_ablations.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.ablation_helpers import (
    METRIC_KEYS,
    AblationSpec,
    build_ablation_specs,
    load_feature_policy_v1,
)
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs
from src.modeling.tournament_registry import append_run, refresh_leaderboard
from src.modeling.train_catboost import fit_catboost_eval
from src.modeling.train_lightgbm import fit_lightgbm_eval


def _run_spec(family: str, spec: AblationSpec) -> dict:
    model_name = f"{family}_{spec.name}"
    kwargs = {
        "drop_cols": list(spec.drop_cols) or None,
        "add_cols": list(spec.add_cols) or None,
        "model_name": model_name,
        "save": False,
    }
    if family == "catboost":
        return fit_catboost_eval(**kwargs)
    return fit_lightgbm_eval(**kwargs)


def _register(family: str, spec: AblationSpec, result: dict) -> None:
    append_run(
        {
            "run_id": f"ablation_{family}_{spec.name}",
            "family": family,
            "model": result.get("model", f"{family}_{spec.name}"),
            "ablation": spec.name,
            "status": result.get("status", "ok"),
            "reason": result.get("reason"),
            "source": "top_model_ablations",
            "split": "val",
            "test_sealed": True,
            **{k: result.get(k) for k in METRIC_KEYS if k in result or result.get("status") == "ok"},
            "pr_auc": result.get("pr_auc"),
            "roc_auc": result.get("roc_auc"),
            "brier": result.get("brier"),
            "ece": result.get("ece"),
            "log_loss": result.get("log_loss"),
            "pr_lift": result.get("pr_lift"),
            "withdrawn_mw_capture_at_10pct": result.get("withdrawn_mw_capture_at_10pct"),
        }
    )


def main() -> int:
    ensure_artifact_dirs()
    policy = load_feature_policy_v1()
    specs = build_ablation_specs(policy)
    families = ("catboost", "lightgbm")
    all_results: dict[str, dict[str, dict]] = {f: {} for f in families}

    for family in families:
        print(f"\n=== {family} ablations ===", flush=True)
        for spec in specs:
            print(f"--- {spec.name}: {spec.description}", flush=True)
            result = _run_spec(family, spec)
            all_results[family][spec.name] = result
            _register(family, spec, result)
            status = result.get("status", "ok")
            if status == "skipped":
                print(f"  SKIPPED: {result.get('reason')}", flush=True)
            else:
                print(
                    f"  pr_auc={result.get('pr_auc'):.4f} log_loss={result.get('log_loss'):.4f} "
                    f"n_features={result.get('n_features')}",
                    flush=True,
                )

    metrics_dir = ARTIFACTS_DIR / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    md_path = metrics_dir / "top_model_ablations.md"

    lines = [
        "# Top-model feature ablations (validation only)",
        "",
        "**Test / score sealed.** All runs on val split only.",
        "",
        f"Policy: `{ARTIFACTS_DIR / 'feature_policy_v1.json'}`",
        "",
    ]
    for family in families:
        lines.append(f"## {family}")
        lines.append("")
        lines.append("| ablation | status | pr_auc | roc_auc | brier | log_loss | n_features | note |")
        lines.append("|----------|--------|--------|---------|-------|----------|------------|------|")
        for spec in specs:
            r = all_results[family][spec.name]
            note = r.get("reason") or r.get("join_note") or spec.description
            lines.append(
                f"| `{spec.name}` | {r.get('status', 'ok')} | {r.get('pr_auc')} | {r.get('roc_auc')} | "
                f"{r.get('brier')} | {r.get('log_loss')} | {r.get('n_features')} | {note} |"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    (metrics_dir / "top_model_ablations.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )
    refresh_leaderboard()
    print(json.dumps({"md": str(md_path), "n_specs": len(specs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
