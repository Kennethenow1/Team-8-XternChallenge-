"""Evaluation protocol helpers for Phase 1 withdrawal models.

Hard rule: score baselines / HPO on **validation** only.
Do not use test for hyperparameter selection or model picking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from src.common.paths import GOLD_DIR, QUALITY_DIR

SPLIT_MANIFEST = GOLD_DIR / "split_manifest.json"
REPORT_DIR = QUALITY_DIR / "modeling"
METRICS_DIR = GOLD_DIR / "modeling" / "artifacts" / "metrics"

SELECTION_SPLIT = "val"
SEALED_SPLITS = frozenset({"test", "score"})

PRIMARY_METRICS = ("pr_auc", "roc_auc", "brier", "ece", "log_loss")


def load_split_manifest(path: Path | None = None) -> dict[str, Any]:
    p = path or SPLIT_MANIFEST
    return json.loads(p.read_text(encoding="utf-8"))


def assert_selection_split(split: str) -> None:
    if split in SEALED_SPLITS:
        raise RuntimeError(
            f"Split '{split}' is sealed for selection/HPO. Use '{SELECTION_SPLIT}' only."
        )


def sanity_baselines(prevalence: float) -> dict[str, float]:
    """No-skill references for a single prevalence (use val prevalence for val PR-AUC)."""
    p = float(prevalence)
    return {
        "prevalence": p,
        "random_rank_pr_auc": p,
        "constant_brier": p * (1.0 - p),
        "constant_roc_auc": 0.5,
    }


def split_sanity_baselines(
    train_prevalence: float,
    val_prevalence: float,
) -> dict[str, Any]:
    """Train descriptive refs + validation no-skill refs (do not mix)."""
    tr = sanity_baselines(train_prevalence)
    va = sanity_baselines(val_prevalence)
    # Brier of predicting train prevalence on val labels
    p_tr, p_va = float(train_prevalence), float(val_prevalence)
    train_p_on_val_brier = (p_tr - p_va) ** 2 + p_va * (1.0 - p_va)  # E[(p_tr - Y)^2]
    # exact: p_va*(1-p_tr)^2 + (1-p_va)*p_tr^2
    train_p_on_val_brier = p_va * (1.0 - p_tr) ** 2 + (1.0 - p_va) * (p_tr**2)
    return {
        "train": tr,
        "val": va,
        "train_prevalence_constant_brier_on_val": float(train_p_on_val_brier),
        "note": (
            "Val no-skill PR-AUC = val prevalence. "
            "Train prevalence is descriptive only — not the val PR-AUC baseline."
        ),
    }


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bins: int = 10,
) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return float("nan")
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        if not np.any(mask):
            continue
        conf = float(y_prob[mask].mean())
        acc = float(y_true[mask].mean())
        ece += (mask.sum() / n) * abs(acc - conf)
    return float(ece)


def classification_metrics(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
    *,
    n_bins: int = 10,
) -> dict[str, float]:
    """PR-AUC, ROC-AUC, Brier, ECE, LogLoss for binary withdraw_next_12m probabilities."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    yp = np.clip(yp, 1e-7, 1.0 - 1e-7)
    out: dict[str, float] = {
        "n": float(len(yt)),
        "positive_rate": float(yt.mean()) if len(yt) else float("nan"),
        "pr_auc": float("nan"),
        "roc_auc": float("nan"),
        "brier": float("nan"),
        "ece": float("nan"),
        "log_loss": float("nan"),
    }
    if len(yt) < 2 or len(np.unique(yt)) < 2:
        return out
    out["pr_auc"] = float(average_precision_score(yt, yp))
    out["roc_auc"] = float(roc_auc_score(yt, yp))
    out["brier"] = float(brier_score_loss(yt, yp))
    out["ece"] = expected_calibration_error(yt, yp, n_bins=n_bins)
    out["log_loss"] = float(log_loss(yt, yp, labels=[0.0, 1.0]))
    return out


def operational_metrics(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
    capacity_mw: pd.Series | np.ndarray | None = None,
    *,
    fracs: tuple[float, ...] = (0.05, 0.10, 0.20),
) -> dict[str, float]:
    """Operational top-risk metrics at risk percentiles (default 5% / 10% / 20%).

    Rank by predicted P(W); take the top frac of projects. User-facing names:

    - Precision@K  → ``precision_at_{pct}pct``
      Fraction of top-risk projects that actually withdraw.
    - Recall@K     → ``recall_at_{pct}pct``
      Fraction of all withdrawals captured in the top-risk group.
    - MW Capture@K → ``withdrawn_mw_capture_at_{pct}pct``
      Fraction of all withdrawn MW captured in that group (needs capacity_mw).

    Also returns ``lift_at_{pct}pct`` (precision / base rate). Primary ops slice
    for Phase 1 reporting is K=10%.
    """
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    n = len(yt)
    out: dict[str, float] = {}
    if n == 0:
        return out
    order = np.argsort(-yp)
    yt_s = yt[order]
    base_rate = float(yt.mean())
    if capacity_mw is not None:
        mw_arr = np.asarray(capacity_mw, dtype=float)[mask]
        mw = np.where(np.isfinite(mw_arr), mw_arr, 0.0)
        mw_s = mw[order]
        withdrawn_mw = mw_s * yt_s
        total_wd_mw = float(withdrawn_mw.sum())
    else:
        mw_s = None
        total_wd_mw = float("nan")
        withdrawn_mw = None

    for frac in fracs:
        k = max(1, int(np.ceil(frac * n)))
        top = yt_s[:k]
        prec = float(top.mean())
        rec = float(top.sum() / yt.sum()) if yt.sum() > 0 else float("nan")
        lift = prec / base_rate if base_rate > 0 else float("nan")
        pct = int(round(frac * 100))
        out[f"precision_at_{pct}pct"] = prec
        out[f"recall_at_{pct}pct"] = rec
        out[f"lift_at_{pct}pct"] = lift
        if mw_s is not None and withdrawn_mw is not None and total_wd_mw > 0:
            out[f"withdrawn_mw_capture_at_{pct}pct"] = float(withdrawn_mw[:k].sum() / total_wd_mw)
        else:
            out[f"withdrawn_mw_capture_at_{pct}pct"] = float("nan")
    return out


def full_eval_metrics(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
    capacity_mw: pd.Series | np.ndarray | None = None,
    *,
    val_prevalence: float | None = None,
) -> dict[str, float]:
    m = classification_metrics(y_true, y_prob)
    m.update(operational_metrics(y_true, y_prob, capacity_mw))
    prev = float(val_prevalence) if val_prevalence is not None else float(m.get("positive_rate") or float("nan"))
    pr = m.get("pr_auc")
    if pr is not None and np.isfinite(pr) and prev and prev > 0:
        m["pr_lift"] = float(pr / prev)
        m["val_prevalence"] = prev
    else:
        m["pr_lift"] = float("nan")
        m["val_prevalence"] = prev
    return m


# --- Tournament goals (validation only) ---

STRONG_GOALS = {
    "pr_auc": 0.10,
    "pr_lift": 2.5,
    "roc_auc": 0.74,
    "log_loss": 0.195,  # upper bound
    "withdrawn_mw_capture_at_10pct": 0.22,
}
STRETCH_GOALS = {
    "pr_auc": 0.12,
    "pr_lift": 3.0,
    "roc_auc": 0.78,
    "log_loss": 0.185,
    "withdrawn_mw_capture_at_10pct": 0.28,
}
KILL_THRESHOLDS = {"pr_auc": 0.06, "roc_auc": 0.60}


def meets_goals(metrics: dict[str, Any], goals: dict[str, float]) -> bool:
    """Higher-is-better except log_loss (upper bound)."""
    for k, thr in goals.items():
        v = metrics.get(k)
        if v is None or not np.isfinite(float(v)):
            return False
        v = float(v)
        if k == "log_loss":
            if v > thr:
                return False
        elif v < thr:
            return False
    return True


def goal_status(metrics: dict[str, Any]) -> str:
    if meets_goals(metrics, STRETCH_GOALS):
        return "stretch"
    if meets_goals(metrics, STRONG_GOALS):
        return "strong"
    return "below_strong"


def distance_to_strong(metrics: dict[str, Any]) -> dict[str, float]:
    out = {}
    for k, thr in STRONG_GOALS.items():
        v = metrics.get(k)
        if v is None or not np.isfinite(float(v)):
            out[f"delta_{k}"] = float("nan")
            continue
        v = float(v)
        if k == "log_loss":
            out[f"delta_{k}"] = thr - v  # positive = under budget
        else:
            out[f"delta_{k}"] = v - thr  # positive = above target
    return out


def calibration_curve_points(
    y_true: pd.Series | np.ndarray,
    y_prob: pd.Series | np.ndarray,
    *,
    n_bins: int = 10,
) -> dict[str, list[float]]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_prob, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]
    if len(yt) < 2 or len(np.unique(yt)) < 2:
        return {"fraction_positive": [], "mean_predicted": []}
    frac, mean_pred = calibration_curve(yt, yp, n_bins=n_bins, strategy="uniform")
    return {
        "fraction_positive": [float(x) for x in frac],
        "mean_predicted": [float(x) for x in mean_pred],
    }


def ensemble_weights_placeholder(model_names: list[str]) -> dict[str, float]:
    if not model_names:
        return {}
    w = 1.0 / len(model_names)
    return {name: w for name in model_names}


def combine_probabilities(
    prob_by_model: dict[str, np.ndarray],
    weights: dict[str, float],
) -> np.ndarray:
    names = [n for n in weights if n in prob_by_model]
    if not names:
        raise ValueError("No overlapping model names between weights and probabilities")
    wsum = sum(weights[n] for n in names)
    if wsum <= 0:
        raise ValueError("Weights must sum to a positive value")
    acc = None
    for n in names:
        piece = np.asarray(prob_by_model[n], dtype=float) * (weights[n] / wsum)
        acc = piece if acc is None else acc + piece
    assert acc is not None
    return acc


def write_leaderboard(
    rows: list[dict[str, Any]],
    *,
    metrics_dir: Path | None = None,
    stem: str = "val_baseline_leaderboard",
    train_prevalence: float | None = None,
    val_prevalence: float | None = None,
    prevalence: float | None = None,  # backward compat: treated as train if val not set
) -> dict[str, Path]:
    """Write CSV + markdown validation leaderboard (selection split only)."""
    metrics_dir = metrics_dir or METRICS_DIR
    metrics_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    csv_path = metrics_dir / f"{stem}.csv"
    md_path = metrics_dir / f"{stem}.md"
    df.to_csv(csv_path, index=False)

    if train_prevalence is None and prevalence is not None:
        train_prevalence = prevalence
    if val_prevalence is None and rows:
        # prefer constant model's positive_rate / n from metrics if present
        for r in rows:
            if r.get("model") == "constant" and r.get("n"):
                # constant PR-AUC equals val prevalence under constant ranking
                if r.get("pr_auc") is not None and np.isfinite(r["pr_auc"]):
                    val_prevalence = float(r["pr_auc"])
                    break

    lines = [
        f"# Validation baseline leaderboard (`{SELECTION_SPLIT}` only)",
        "",
        "**Test / score are sealed** — do not use for HPO or model selection.",
        "",
    ]
    if train_prevalence is not None or val_prevalence is not None:
        lines.extend(["## Sanity baselines", ""])
        if train_prevalence is not None:
            tr = sanity_baselines(train_prevalence)
            lines.extend(
                [
                    f"- **Train** prevalence (descriptive) ≈ **{tr['prevalence']:.4f}**",
                    f"- Train-prevalence constant Brier on train ≈ **{tr['constant_brier']:.4f}**",
                    "",
                ]
            )
        if val_prevalence is not None:
            va = sanity_baselines(val_prevalence)
            lines.extend(
                [
                    f"- **Validation** prevalence ≈ **{va['prevalence']:.4f}**",
                    f"- **Val no-skill PR-AUC baseline** ≈ **{va['random_rank_pr_auc']:.4f}** (use this, not train prevalence)",
                    f"- Val constant-p_val Brier ≈ **{va['constant_brier']:.4f}**",
                    f"- Constant ROC-AUC = **{va['constant_roc_auc']:.3f}**",
                    "",
                ]
            )
        if train_prevalence is not None and val_prevalence is not None:
            sb = split_sanity_baselines(train_prevalence, val_prevalence)
            lines.extend(
                [
                    f"- Train-prevalence constant Brier **on val** ≈ **{sb['train_prevalence_constant_brier_on_val']:.4f}** "
                    "(matches evaluating train prevalence against a lower-prevalence future period)",
                    "",
                ]
            )
    lines.append("| " + " | ".join(df.columns.astype(str)) + " |")
    lines.append("| " + " | ".join(["---"] * len(df.columns)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in df.columns) + " |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"csv": csv_path, "md": md_path}


def protocol_notes() -> str:
    manifest: dict[str, Any] = {}
    if SPLIT_MANIFEST.exists():
        manifest = load_split_manifest()
    return "\n".join(
        [
            "# Evaluation protocol (Phase 1)",
            "",
            "Fixed temporal splits only. Do not use random CV.",
            "",
            f"- train_years: {manifest.get('train_years', [2020, 2021, 2022])}",
            f"- validation_year: {manifest.get('validation_year', 2023)}",
            f"- test_year: {manifest.get('test_year', 2024)}",
            "",
            f"**Selection split: `{SELECTION_SPLIT}`.** Splits `{sorted(SEALED_SPLITS)}` are sealed until the architecture is frozen.",
            "",
            "Primary metrics: PR-AUC, ROC-AUC, Brier, ECE, LogLoss.",
            "Operational: Precision@5/10%, Recall@10%, Lift@10%, Withdrawn-MW-Capture@10%.",
            "HPO objective: PR-AUC with Brier/ECE/LogLoss tie-break.",
            "Tree early stopping: LogLoss.",
            "",
            "Sanity on **val**: no-skill PR-AUC ≈ **val** prevalence (~0.041), not train (~0.124).",
            "",
            "See `docs/model_architecture.md` and `docs/modeling_experiment_protocol.md`.",
            "",
        ]
    )


def write_protocol_notes(report_dir: Path | None = None) -> Path:
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "eval_protocol.md"
    path.write_text(protocol_notes(), encoding="utf-8")
    return path
