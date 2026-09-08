"""Unified tournament registry: all_runs, leaderboard, champion, live HPO logs."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.modeling.eval_protocol import (
    METRICS_DIR,
    STRONG_GOALS,
    STRETCH_GOALS,
    distance_to_strong,
    goal_status,
)
from src.modeling.model_registry import ARTIFACTS_DIR, ensure_artifact_dirs

ALL_RUNS_PATH = ARTIFACTS_DIR / "all_runs.parquet"
LEADERBOARD_CSV = METRICS_DIR / "validation_leaderboard.csv"
LEADERBOARD_MD = METRICS_DIR / "validation_leaderboard.md"
CHAMPION_PATH = ARTIFACTS_DIR / "champion.json"
GOAL_STATUS_PATH = METRICS_DIR / "goal_status.json"

FAMILY_CEILINGS = {
    "catboost": 1500,
    "lightgbm": 800,
    "xgboost": 800,
    "tabm": 700,
    "logistic": 100,
    "tabpfn": 50,
    "tabicl": 50,
    "survival_boost": 700,
}

FAMILY_MIN_FAIR = {
    "catboost": 200,
    "lightgbm": 150,
    "xgboost": 150,
    "tabm": 150,
    "logistic": 30,
    "tabpfn": 20,
    "tabicl": 20,
    "survival_boost": 150,
}

SEEDS = (13, 42, 73, 101, 2026)


def hpo_dir(family: str) -> Path:
    d = ARTIFACTS_DIR / "hpo" / family
    d.mkdir(parents=True, exist_ok=True)
    return d


def study_db_url(family: str) -> str:
    return f"sqlite:///{hpo_dir(family) / 'study.db'}"


def live_trials_path(family: str) -> Path:
    return hpo_dir(family) / "live_trials.jsonl"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_run(record: dict[str, Any]) -> None:
    """Append one run to all_runs.parquet."""
    ensure_artifact_dirs()
    row = {k: v for k, v in dict(record).items() if v is not None}
    row.setdefault("recorded_at", _utcnow())
    row.setdefault("split", "val")
    row.setdefault("test_sealed", True)
    if "pr_auc" in row and "goal" not in row:
        row["goal"] = goal_status(row)
    df_new = pd.DataFrame([row])
    if ALL_RUNS_PATH.exists():
        prev = pd.read_parquet(ALL_RUNS_PATH)
        df = pd.concat([prev, df_new], ignore_index=True, sort=False)
    else:
        df = df_new
    df.to_parquet(ALL_RUNS_PATH, index=False)


def load_all_runs() -> pd.DataFrame:
    if not ALL_RUNS_PATH.exists():
        return pd.DataFrame()
    return pd.read_parquet(ALL_RUNS_PATH)


def append_live_trial(family: str, payload: dict[str, Any]) -> None:
    path = live_trials_path(family)
    line = json.dumps({**payload, "ts": _utcnow()}, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(
        f"[{family}] trial={payload.get('trial')} "
        f"pr={payload.get('pr_auc')} lift={payload.get('pr_lift')} "
        f"roc={payload.get('roc_auc')} ll={payload.get('log_loss')} "
        f"mw10={payload.get('withdrawn_mw_capture_at_10pct')} "
        f"best={payload.get('best_pr_auc')} goal={payload.get('goal')} "
        f"plateau={payload.get('plateau')}",
        flush=True,
    )


def composite_score(row: dict[str, Any] | pd.Series) -> float:
    """Higher better: PR + ROC - LogLoss - Brier (+ small MW bonus)."""
    pr = float(row.get("pr_auc") or 0.0)
    roc = float(row.get("roc_auc") or 0.0)
    ll = float(row.get("log_loss") or 1.0)
    br = float(row.get("brier") or 1.0)
    mw = float(row.get("withdrawn_mw_capture_at_10pct") or 0.0)
    if not all(map(lambda x: x == x, [pr, roc, ll, br])):  # NaN check
        return float("-inf")
    return pr + 0.15 * roc - 0.5 * ll - 0.25 * br + 0.05 * mw


def refresh_leaderboard() -> pd.DataFrame:
    """Best ok run per model/family → validation_leaderboard."""
    ensure_artifact_dirs()
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_all_runs()
    if df.empty:
        empty = pd.DataFrame()
        empty.to_csv(LEADERBOARD_CSV, index=False)
        LEADERBOARD_MD.write_text("# Validation leaderboard\n\n(no runs yet)\n", encoding="utf-8")
        return empty

    status = df["status"] if "status" in df.columns else pd.Series(["ok"] * len(df))
    ok = df[status.fillna("ok") == "ok"].copy()
    if ok.empty:
        ok = df.copy()
    ok = ok[ok.get("pr_auc", pd.Series(dtype=float)).notna()].copy() if "pr_auc" in ok.columns else ok
    if ok.empty:
        empty = pd.DataFrame()
        empty.to_csv(LEADERBOARD_CSV, index=False)
        LEADERBOARD_MD.write_text("# Validation leaderboard\n\n(no successful runs)\n", encoding="utf-8")
        return empty

    ok["_score"] = ok.apply(composite_score, axis=1)
    key = "model" if "model" in ok.columns else "family"
    ok[key] = ok[key].fillna("unknown").astype(str)
    best_idx = ok.groupby(key, dropna=False)["_score"].idxmax()
    best_idx = best_idx.dropna()
    board = ok.loc[best_idx].sort_values("_score", ascending=False)

    cols = [
        c
        for c in (
            "model",
            "family",
            "status",
            "pr_auc",
            "pr_lift",
            "roc_auc",
            "brier",
            "ece",
            "log_loss",
            "withdrawn_mw_capture_at_10pct",
            "precision_at_10pct",
            "recall_at_10pct",
            "goal",
            "seed",
            "run_id",
        )
        if c in board.columns
    ]
    board[cols].to_csv(LEADERBOARD_CSV, index=False)

    lines = [
        "# Validation tournament leaderboard",
        "",
        "**Test / score sealed.** Selection on val only.",
        "",
        f"- Strong goals: `{json.dumps(STRONG_GOALS)}`",
        f"- Stretch goals: `{json.dumps(STRETCH_GOALS)}`",
        "",
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, r in board.iterrows():
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    lines.append("")
    LEADERBOARD_MD.write_text("\n".join(lines), encoding="utf-8")

    # Champion
    top = board.iloc[0]
    champ = {c: (None if pd.isna(top.get(c)) else top.get(c)) for c in cols}
    champ["composite_score"] = float(top["_score"])
    champ["updated_at"] = _utcnow()
    champ["test_sealed"] = True
    CHAMPION_PATH.write_text(json.dumps(champ, indent=2, default=str), encoding="utf-8")

    # Goal status by family
    goal_map: dict[str, Any] = {}
    fam_col = "family" if "family" in ok.columns else key
    ok2 = ok.copy()
    ok2[fam_col] = ok2[fam_col].fillna("unknown").astype(str)
    for fam, g in ok2.groupby(fam_col):
        if g["_score"].isna().all() or len(g) == 0:
            continue
        idx = g["_score"].idxmax()
        if pd.isna(idx):
            continue
        best = g.loc[idx]
        m = best.to_dict()
        goal_map[str(fam)] = {
            "goal": goal_status(m),
            "pr_auc": m.get("pr_auc"),
            "pr_lift": m.get("pr_lift"),
            "roc_auc": m.get("roc_auc"),
            "log_loss": m.get("log_loss"),
            "withdrawn_mw_capture_at_10pct": m.get("withdrawn_mw_capture_at_10pct"),
            "deltas": distance_to_strong(m),
            "n_runs": int(len(g)),
        }
    GOAL_STATUS_PATH.write_text(json.dumps(goal_map, indent=2, default=str), encoding="utf-8")
    return board


def plateau_detected(
    pr_history: list[float],
    *,
    window: int = 100,
    min_delta: float = 0.002,
) -> bool:
    if len(pr_history) < window + 1:
        return False
    recent = pr_history[-window:]
    prior_best = max(pr_history[:-window]) if pr_history[:-window] else recent[0]
    return (max(recent) - prior_best) < min_delta


def should_stop_family(
    family: str,
    *,
    n_completed: int,
    best_metrics: dict[str, Any],
    pr_history: list[float],
    stretch_push: bool = False,
) -> tuple[bool, str]:
    """Goal-aware stop. Returns (stop, reason)."""
    ceiling = FAMILY_CEILINGS.get(family, 500)
    min_fair = FAMILY_MIN_FAIR.get(family, 50)
    g = goal_status(best_metrics) if best_metrics else "below_strong"

    if n_completed >= ceiling:
        return True, "ceiling"

    if g == "stretch":
        return True, "stretch_attained"

    if g == "strong" and not stretch_push:
        return True, "strong_attained_stabilize"

    if n_completed >= min_fair and plateau_detected(pr_history):
        return True, "plateau"

    # Kill rule for weak families after min fair
    if n_completed >= min_fair and best_metrics:
        pr = float(best_metrics.get("pr_auc") or 0)
        roc = float(best_metrics.get("roc_auc") or 0)
        if pr < 0.06 and roc < 0.60:
            return True, "kill_near_random"

    return False, ""


def ingest_existing_artifacts() -> dict[str, int]:
    """Load baseline + catboost HPO trials into all_runs if empty/missing."""
    ensure_artifact_dirs()
    counts = {"baselines": 0, "catboost_trials": 0}

    # Baselines from leaderboard summary or model metrics.json
    models_root = ARTIFACTS_DIR / "models"
    if models_root.exists():
        for d in models_root.iterdir():
            mj = d / "metrics.json"
            if not mj.exists():
                continue
            m = json.loads(mj.read_text(encoding="utf-8"))
            if m.get("status") not in (None, "ok"):
                continue
            append_run(
                {
                    "run_id": f"baseline_{d.name}",
                    "family": d.name.split("_")[0] if d.name.startswith("logistic") else d.name.replace("_tuned", "").replace("_v1_minus_macro", ""),
                    "model": d.name,
                    "status": m.get("status", "ok"),
                    "source": "artifact_metrics",
                    **{k: m.get(k) for k in (
                        "pr_auc", "roc_auc", "brier", "ece", "log_loss", "n",
                        "precision_at_5pct", "precision_at_10pct", "precision_at_20pct",
                        "recall_at_5pct", "recall_at_10pct", "recall_at_20pct",
                        "lift_at_5pct", "lift_at_10pct", "lift_at_20pct",
                        "withdrawn_mw_capture_at_5pct", "withdrawn_mw_capture_at_10pct",
                        "withdrawn_mw_capture_at_20pct", "pr_lift", "positive_rate",
                    ) if k in m or True},
                }
            )
            counts["baselines"] += 1

    trials_csv = ARTIFACTS_DIR / "hpo" / "catboost" / "trials.csv"
    if trials_csv.exists():
        tdf = pd.read_csv(trials_csv)
        for _, r in tdf.iterrows():
            rec = r.to_dict()
            append_run(
                {
                    "run_id": f"catboost_hpo_trial_{int(rec.get('trial', -1))}",
                    "family": "catboost",
                    "model": "catboost_hpo",
                    "status": "ok",
                    "source": "hpo_trials_csv",
                    "trial": rec.get("trial"),
                    **{k: rec.get(k) for k in rec},
                }
            )
            counts["catboost_trials"] += 1

    refresh_leaderboard()
    return counts
