#!/usr/bin/env python3
"""Survival tournament smoke + optional boosted HPO hook (val-only).

  python scripts/run_survival_tournament.py [--smoke-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs
from src.modeling.tournament_registry import append_run, refresh_leaderboard
from src.modeling.train_survival import (
    fit_boosted_discrete_hazard,
    fit_cox_ph,
    fit_cox_tv,
    fit_discrete_logistic_hazard,
    fit_random_survival_forest,
    fit_xgb_aft,
)


def _register(name: str, result: dict) -> None:
    append_run(
        {
            "run_id": f"survival_{name}",
            "family": "survival",
            "model": result.get("model", name),
            "status": result.get("status", "ok"),
            "reason": result.get("reason"),
            "source": "survival_tournament",
            "split": "val",
            "test_sealed": True,
            "pr_auc": result.get("pr_auc"),
            "roc_auc": result.get("roc_auc"),
            "brier": result.get("brier"),
            "log_loss": result.get("log_loss"),
            "ece": result.get("ece"),
            "precision_at_10pct": result.get("precision_at_10pct"),
            "recall_at_10pct": result.get("recall_at_10pct"),
            "withdrawn_mw_capture_at_10pct": result.get("withdrawn_mw_capture_at_10pct"),
            "alignment": result.get("alignment"),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true", help="Run default discrete logistic only")
    args = parser.parse_args()

    ensure_artifact_dirs()
    runners = [
        ("discrete_logistic", fit_discrete_logistic_hazard),
    ]
    if not args.smoke_only:
        # Phase 1 core: Cox-TV first, then static Cox / discrete / AFT / RSF
        runners.extend(
            [
                ("cox_tv", fit_cox_tv),
                ("cox_ph", fit_cox_ph),
                ("boost_lgbm", fit_boosted_discrete_hazard),
                ("xgb_aft", fit_xgb_aft),
                ("rsf", fit_random_survival_forest),
            ]
        )

    results = {}
    for name, fn in runners:
        print(f"=== survival/{name} ===", flush=True)
        r = fn(save=True)
        results[name] = r
        _register(name, r)
        if r.get("status") == "skipped":
            print(f"  SKIPPED: {r.get('reason')}", flush=True)
        else:
            print(
                f"  pr_auc={r.get('pr_auc')} alignment={r.get('alignment')}",
                flush=True,
            )

    out = ARTIFACTS_DIR / "metrics" / "survival_tournament.md"
    lines = [
        "# Survival tournament (validation only)",
        "",
        "**Test / score sealed.** 12m risk aligned to modeling val where possible.",
        "",
        "| model | status | pr_auc | roc_auc | P@10% | R@10% | MW@10% | alignment |",
        "|-------|--------|--------|---------|-------|-------|--------|-----------|",
    ]
    for name, r in results.items():
        lines.append(
            f"| {name} | {r.get('status')} | {r.get('pr_auc')} | {r.get('roc_auc')} | "
            f"{r.get('precision_at_10pct')} | {r.get('recall_at_10pct')} | "
            f"{r.get('withdrawn_mw_capture_at_10pct')} | "
            f"{r.get('alignment', r.get('reason', ''))} |"
        )
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    refresh_leaderboard()
    print(json.dumps({"md": str(out), "results": {k: v.get("status") for k, v in results.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
