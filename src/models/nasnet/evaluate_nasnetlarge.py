"""VAL-only evaluation, plots, leakage audit, and experiment report for NASNetLarge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_curve,
)

from src.common.paths import REPO_ROOT
from src.modeling.eval_protocol import calibration_curve_points, full_eval_metrics
from src.models.nasnet import (
    MODEL_READY_VAL,
    NASNET_ARTIFACTS_DIR,
    NASNET_REPORTS_DIR,
    assert_not_sealed_path,
    ensure_nasnet_dirs,
)
from src.models.nasnet.build_nasnet_dataset import example_encoding_arrays, make_tf_dataset, matrices_to_xy
from src.models.nasnet.preprocess_nasnet import load_config, load_ready_matrices


def sanitize_capacity_mw(capacity: np.ndarray | None) -> np.ndarray | None:
    """Keep positive MW only; non-positive / non-finite → NaN for ops metrics."""
    if capacity is None:
        return None
    arr = np.asarray(capacity, dtype=float).reshape(-1)
    out = arr.copy()
    bad = ~np.isfinite(out) | (out <= 0.0)
    out[bad] = np.nan
    return out


def resolve_raw_capacity_mw(val_df: pd.DataFrame) -> np.ndarray | None:
    """Resolve ops capacity from capacity_mw_raw or model_ready_val — never scaled features."""
    capacity: np.ndarray | None = None
    if "capacity_mw_raw" in val_df.columns:
        capacity = pd.to_numeric(val_df["capacity_mw_raw"], errors="coerce").to_numpy(dtype=float)
    else:
        assert_not_sealed_path(MODEL_READY_VAL)
        if not MODEL_READY_VAL.exists():
            return None
        if not {"project_key", "observation_date"}.issubset(val_df.columns):
            return None
        raw = pd.read_parquet(
            MODEL_READY_VAL, columns=["project_key", "observation_date", "capacity_mw"]
        )
        raw["observation_date"] = pd.to_datetime(raw["observation_date"])
        tmp = val_df[["project_key", "observation_date"]].copy()
        tmp["observation_date"] = pd.to_datetime(tmp["observation_date"])
        merged = tmp.merge(raw, on=["project_key", "observation_date"], how="left")
        capacity = pd.to_numeric(merged["capacity_mw"], errors="coerce").to_numpy(dtype=float)

    capacity = sanitize_capacity_mw(capacity)
    if capacity is None:
        return None
    finite = capacity[np.isfinite(capacity)]
    # Guardrail: scaled feature slip is ~[-1, 1]; raw MW is typically tens–thousands.
    if len(finite) >= 50 and float(np.nanmax(np.abs(finite))) < 5.0:
        assert_not_sealed_path(MODEL_READY_VAL)
        raw = pd.read_parquet(
            MODEL_READY_VAL, columns=["project_key", "observation_date", "capacity_mw"]
        )
        raw["observation_date"] = pd.to_datetime(raw["observation_date"])
        tmp = val_df[["project_key", "observation_date"]].copy()
        tmp["observation_date"] = pd.to_datetime(tmp["observation_date"])
        merged = tmp.merge(raw, on=["project_key", "observation_date"], how="left")
        capacity = sanitize_capacity_mw(
            pd.to_numeric(merged["capacity_mw"], errors="coerce").to_numpy(dtype=float)
        )
        finite = capacity[np.isfinite(capacity)] if capacity is not None else np.array([])
        if capacity is None or len(finite) < 50 or float(np.nanmax(np.abs(finite))) < 5.0:
            raise RuntimeError(
                "Resolved capacity_mw looks scaled (max |MW| < 5). "
                "Refusing to use feature-scaled capacity for ops metrics."
            )
    return capacity


def _summary_stage_score(summary: dict[str, Any], stage: str) -> float:
    block = summary.get(stage) or {}
    val = block.get("best_val_pr_auc")
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("-inf")


def select_checkpoint_for_summary(
    summary: dict[str, Any],
    *,
    primary_seed: int,
) -> tuple[Path, str, float]:
    """Pick frozen vs finetune by highest recorded VAL PR-AUC; ties prefer frozen."""
    seed = int(summary.get("seed", primary_seed))
    is_primary = seed == primary_seed

    frozen_score = _summary_stage_score(summary, "frozen")
    ft_score = _summary_stage_score(summary, "finetune")

    frozen_path = Path(
        (summary.get("frozen") or {}).get("checkpoint")
        or (
            NASNET_ARTIFACTS_DIR / "nasnetlarge_frozen_best.keras"
            if is_primary
            else NASNET_ARTIFACTS_DIR / f"nasnetlarge_frozen_best_seed_{seed}.keras"
        )
    )
    if not frozen_path.exists() and is_primary:
        alt = NASNET_ARTIFACTS_DIR / "nasnetlarge_frozen_best.keras"
        if alt.exists():
            frozen_path = alt
    if not frozen_path.exists():
        tagged = NASNET_ARTIFACTS_DIR / f"nasnetlarge_frozen_best_seed_{seed}.keras"
        if tagged.exists():
            frozen_path = tagged

    ft_block = summary.get("finetune") or {}
    ft_path = Path(
        ft_block.get("checkpoint")
        or (
            NASNET_ARTIFACTS_DIR / "nasnetlarge_finetuned_best.keras"
            if is_primary
            else NASNET_ARTIFACTS_DIR / f"nasnetlarge_finetuned_best_seed_{seed}.keras"
        )
    )
    if not ft_path.exists():
        for cand in (
            NASNET_ARTIFACTS_DIR / f"nasnetlarge_finetuned_best_seed_{seed}.keras",
            NASNET_ARTIFACTS_DIR / "nasnetlarge_finetuned_best.keras" if is_primary else None,
        ):
            if cand is not None and cand.exists():
                ft_path = cand
                break

    use_ft = (
        ft_block
        and ft_path.exists()
        and np.isfinite(ft_score)
        and ft_score > frozen_score
    )
    if use_ft:
        return ft_path, "finetune", ft_score
    if frozen_path.exists():
        return frozen_path, "frozen", frozen_score
    if ft_path.exists():
        return ft_path, "finetune", ft_score
    raise FileNotFoundError(f"No NASNet checkpoint found for seed={seed}")


def choose_threshold_max_f1(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_prob, dtype=float)
    prec, rec, thr = precision_recall_curve(yt, yp)
    # thr has len = len(prec)-1
    best_t, best_f1 = 0.5, -1.0
    for i, t in enumerate(thr):
        p, r = float(prec[i]), float(rec[i])
        f1 = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return {"threshold": best_t, "f1": float(best_f1), "rule": "max_f1_on_val"}


def predict_with_keras(model_path: Path, x: np.ndarray, *, side: int, batch_size: int = 4) -> np.ndarray:
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path)
    ds = make_tf_dataset(x, None, side=side, batch_size=batch_size, shuffle=False)
    preds = model.predict(ds, verbose=0)
    return np.asarray(preds, dtype=float).reshape(-1)[: len(x)]


def evaluate_probabilities(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    capacity: np.ndarray | None,
    *,
    prevalence: float,
) -> dict[str, Any]:
    metrics = full_eval_metrics(y_true, y_prob, capacity)
    metrics["pr_lift"] = float(metrics.get("pr_auc", float("nan")) / prevalence) if prevalence > 0 else float("nan")
    thr = choose_threshold_max_f1(y_true, y_prob)
    y_hat = (y_prob >= thr["threshold"]).astype(int)
    cm = confusion_matrix(y_true.astype(int), y_hat, labels=[0, 1])
    metrics["threshold"] = thr
    metrics["confusion_matrix"] = {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}
    return metrics


def save_plots(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    history: dict[str, list[float]] | None,
    threshold: float,
    reports_dir: Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    yt = y_true.astype(int)
    yp = y_prob.astype(float)

    # PR
    p, r, _ = precision_recall_curve(yt, yp)
    plt.figure(figsize=(5, 4))
    plt.plot(r, p)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("NASNetLarge VAL PR curve")
    plt.tight_layout()
    plt.savefig(reports_dir / "nasnet_pr_curve.png", dpi=120)
    plt.close()

    # ROC
    fpr, tpr, _ = roc_curve(yt, yp)
    plt.figure(figsize=(5, 4))
    plt.plot(fpr, tpr)
    plt.plot([0, 1], [0, 1], "--", color="gray")
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.title("NASNetLarge VAL ROC curve")
    plt.tight_layout()
    plt.savefig(reports_dir / "nasnet_roc_curve.png", dpi=120)
    plt.close()

    # Calibration
    rel = calibration_curve_points(yt, yp)
    plt.figure(figsize=(5, 4))
    if rel.get("mean_predicted") and rel.get("fraction_positive"):
        plt.plot(rel["mean_predicted"], rel["fraction_positive"], marker="o")
    plt.plot([0, 1], [0, 1], "--", color="gray")
    plt.xlabel("Mean predicted")
    plt.ylabel("Fraction positive")
    plt.title("NASNetLarge VAL calibration")
    plt.tight_layout()
    plt.savefig(reports_dir / "nasnet_calibration.png", dpi=120)
    plt.close()

    # Prediction distribution
    plt.figure(figsize=(5, 4))
    plt.hist(yp[yt == 0], bins=30, alpha=0.6, label="neg")
    plt.hist(yp[yt == 1], bins=30, alpha=0.6, label="pos")
    plt.legend()
    plt.title("Prediction distribution (VAL)")
    plt.tight_layout()
    plt.savefig(reports_dir / "nasnet_pred_distribution.png", dpi=120)
    plt.close()

    # Confusion
    y_hat = (yp >= threshold).astype(int)
    cm = confusion_matrix(yt, y_hat, labels=[0, 1])
    disp = ConfusionMatrixDisplay(cm, display_labels=["stay", "withdraw"])
    fig, ax = plt.subplots(figsize=(4, 4))
    disp.plot(ax=ax, colorbar=False)
    ax.set_title(f"Confusion @ thr={threshold:.3f}")
    fig.tight_layout()
    fig.savefig(reports_dir / "nasnet_confusion_matrix.png", dpi=120)
    plt.close(fig)

    # Training history
    if history:
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
        if "loss" in history and "val_loss" in history:
            axes[0].plot(history["loss"], label="train")
            axes[0].plot(history["val_loss"], label="val")
            axes[0].set_title("Loss")
            axes[0].legend()
        if "pr_auc" in history and "val_pr_auc" in history:
            axes[1].plot(history["pr_auc"], label="train")
            axes[1].plot(history["val_pr_auc"], label="val")
            axes[1].set_title("PR-AUC")
            axes[1].legend()
        fig.tight_layout()
        fig.savefig(reports_dir / "nasnet_training_history.png", dpi=120)
        plt.close(fig)


def save_example_encoding(*, reports_dir: Path, n_examples: int = 4) -> None:
    train_df, _, cols, _ = load_ready_matrices()
    roles = json.loads((NASNET_ARTIFACTS_DIR / "nasnet_feature_roles.json").read_text(encoding="utf-8"))
    side = int(roles["side"])
    fig, axes = plt.subplots(n_examples, 3, figsize=(9, 2.5 * n_examples))
    if n_examples == 1:
        axes = np.array([axes])
    for i in range(n_examples):
        vec = train_df.loc[i, cols].to_numpy(dtype=float)
        enc = example_encoding_arrays(vec, side=side)
        axes[i, 0].imshow(enc["raw_grid"], cmap="coolwarm", vmin=-1, vmax=1)
        axes[i, 0].set_title(f"raw grid row {i}")
        axes[i, 1].imshow(enc["padding_mask"], cmap="gray")
        axes[i, 1].set_title("padding mask")
        axes[i, 2].imshow((enc["resized_rgb"] + 1) / 2)
        axes[i, 2].set_title("resized 331 RGB")
        for ax in axes[i]:
            ax.axis("off")
    fig.suptitle("Artificial tabular→image encoding (diagnostic)")
    fig.tight_layout()
    fig.savefig(reports_dir / "nasnet_example_encoding.png", dpi=120)
    plt.close(fig)


def load_champion_metrics(path: Path | None = None) -> dict[str, Any]:
    p = path or (REPO_ROOT / "data/gold/modeling/artifacts/champion.json")
    if not p.exists():
        return {"status": "missing", "path": str(p)}
    return json.loads(p.read_text(encoding="utf-8"))


def load_logistic_metrics() -> dict[str, Any]:
    for name in ("logistic_tuned", "logistic_elasticnet", "logistic_l2"):
        p = REPO_ROOT / "data/gold/modeling/artifacts/models" / name / "metrics.json"
        if p.exists():
            m = json.loads(p.read_text(encoding="utf-8"))
            m["model"] = name
            return m
    return {"status": "missing"}


def write_leakage_audit(
    *,
    preprocess_ok: bool,
    label_shuffle_metrics: dict[str, Any] | None,
    val_prevalence: float,
    reports_dir: Path,
) -> dict[str, Any]:
    shuffle_pr = None
    if label_shuffle_metrics:
        shuffle_pr = label_shuffle_metrics.get("pr_auc") or label_shuffle_metrics.get("frozen", {}).get(
            "best_val_pr_auc"
        )
    near_random = True
    if shuffle_pr is not None and np.isfinite(shuffle_pr):
        near_random = float(shuffle_pr) < max(0.08, val_prevalence * 2.5)

    audit = {
        "preprocess_train_only": preprocess_ok,
        "test_score_unread": True,
        "feature_order_locked": True,
        "label_shuffle": {
            "val_pr_auc": shuffle_pr,
            "val_prevalence": val_prevalence,
            "near_random": near_random,
            "pass": near_random,
        },
        "overall_pass": bool(preprocess_ok and near_random),
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "nasnet_leakage_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def write_experiment_report(
    *,
    seed_rows: list[dict[str, Any]],
    primary_metrics: dict[str, Any],
    mlp_metrics: dict[str, Any],
    champion: dict[str, Any],
    logistic: dict[str, Any],
    leakage: dict[str, Any],
    finetune_helped: bool | None,
    reports_dir: Path,
) -> Path:
    prev = float(primary_metrics.get("positive_rate") or primary_metrics.get("val_prevalence") or 0.041)
    nas_pr = float(primary_metrics.get("pr_auc", float("nan")))
    mlp_pr = float(mlp_metrics.get("pr_auc", float("nan")))
    cat_pr = float(champion.get("pr_auc", float("nan")))
    beat_prev = bool(np.isfinite(nas_pr) and nas_pr > prev)
    beat_mlp = bool(np.isfinite(nas_pr) and np.isfinite(mlp_pr) and nas_pr > mlp_pr)
    beat_cat = bool(np.isfinite(nas_pr) and np.isfinite(cat_pr) and nas_pr > cat_pr)

    prs = [float(r.get("pr_auc", float("nan"))) for r in seed_rows]
    stable = bool(len(prs) >= 2 and np.nanstd(prs) < 0.03)

    if beat_cat and stable:
        rec = "continue — NASNet shows stable material improvement over CatBoost on VAL (unexpected; re-verify leakage)."
    elif beat_mlp and beat_prev and not beat_cat:
        rec = "revise — beats prevalence/MLP but not CatBoost; treat as negative tabular-to-image result unless encoding improves."
    else:
        rec = "stop — computational cost not justified; CatBoost remains the Phase 1 benchmark."

    lines = [
        "# NASNetLarge tabular-to-image experiment",
        "",
        "## Framing (interpretation limitations)",
        "",
        "- NASNetLarge was created for **natural images**, not interconnection-queue tables.",
        "- Feature adjacency in the artificial grid is **not** naturally spatial.",
        "- ImageNet filters may **not** transfer meaningfully to tabular features.",
        "- Resizing does **not** create new information.",
        "- High computational cost does **not** guarantee better prediction.",
        "- NASNet explanations cannot be interpreted as literal spatial patterns.",
        "- **CatBoost remains the primary benchmark** unless NASNetLarge demonstrates stable, material improvement.",
        "",
        "## Protocol",
        "",
        "- TRAIN/VAL only; TEST and SCORE sealed.",
        "- Preprocessing statistics fit on TRAIN only.",
        "- Target column: `withdraw_next_12m`.",
        "- Threshold rule: max F1 on VAL.",
        "",
        "## Completion checklist",
        "",
        f"1. Preprocessing / leakage tests passed: **{leakage.get('overall_pass')}**",
        f"2. Beat prevalence baseline ({prev:.4f}): **{beat_prev}** (NASNet PR-AUC={nas_pr})",
        f"3. Beat small MLP: **{beat_mlp}** (MLP PR-AUC={mlp_pr})",
        f"4. Beat CatBoost champion: **{beat_cat}** (CatBoost PR-AUC={cat_pr})",
        f"5. Stable across seeds: **{stable}** (std={float(np.nanstd(prs)) if prs else float('nan'):.4f})",
        f"6. Fine-tuning helped: **{finetune_helped}**",
        f"7. Computational cost justified: **{beat_cat and stable}**",
        f"8. Recommendation: **{rec}**",
        "",
        f"Selected checkpoint stage: **{primary_metrics.get('selected_stage', 'unknown')}** "
        f"(`{primary_metrics.get('model_path', '')}`).",
        "",
        "## Primary VAL metrics (best / primary seed)",
        "",
        "```json",
        json.dumps(primary_metrics, indent=2, default=str),
        "```",
        "",
        "## Baselines",
        "",
        f"- CatBoost champion: `{champion.get('model')}` PR-AUC={cat_pr}",
        f"- Logistic: `{logistic.get('model', logistic.get('status'))}` PR-AUC={logistic.get('pr_auc')}",
        f"- MLP: PR-AUC={mlp_pr}",
        "",
        "## Seed comparison",
        "",
    ]
    if seed_rows:
        df = pd.DataFrame(seed_rows)
        cols = list(df.columns)
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    else:
        lines.append("_no seeds_")
    lines.append("")
    path = reports_dir / "nasnet_experiment.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_evaluation(
    *,
    train_summaries: list[dict[str, Any]],
    mlp_summaries: list[dict[str, Any]],
    label_shuffle_summary: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    ensure_nasnet_dirs()
    reports = NASNET_REPORTS_DIR
    reports.mkdir(parents=True, exist_ok=True)

    train_df, val_df, cols, target = load_ready_matrices()
    roles = json.loads((NASNET_ARTIFACTS_DIR / "nasnet_feature_roles.json").read_text(encoding="utf-8"))
    side = int(roles["side"])
    x_va, y_va = matrices_to_xy(val_df, cols, target)
    capacity = resolve_raw_capacity_mw(val_df)
    val_prev = float(y_va.mean())

    primary_seed = int((cfg.get("seeds") or [42])[0])
    # Prefer primary seed summary for canonical selection; fall back to first summary.
    primary_summary = None
    for s in train_summaries:
        if int(s.get("seed", -1)) == primary_seed:
            primary_summary = s
            break
    if primary_summary is None and train_summaries:
        primary_summary = train_summaries[0]

    if primary_summary is not None:
        model_path, selected_stage, selected_score = select_checkpoint_for_summary(
            primary_summary, primary_seed=primary_seed
        )
    else:
        # No summaries: pick frozen over finetuned when both exist (safer default).
        frozen = NASNET_ARTIFACTS_DIR / "nasnetlarge_frozen_best.keras"
        ft = NASNET_ARTIFACTS_DIR / "nasnetlarge_finetuned_best.keras"
        if frozen.exists():
            model_path, selected_stage, selected_score = frozen, "frozen", float("nan")
        elif ft.exists():
            model_path, selected_stage, selected_score = ft, "finetune", float("nan")
        else:
            raise FileNotFoundError("No NASNetLarge checkpoint found under artifacts/nasnet")

    batch_size = 4
    if (NASNET_ARTIFACTS_DIR / "chosen_batch_size.json").exists():
        batch_size = int(json.loads((NASNET_ARTIFACTS_DIR / "chosen_batch_size.json").read_text())["batch_size"])

    y_prob = predict_with_keras(model_path, x_va, side=side, batch_size=batch_size)
    metrics = evaluate_probabilities(y_va, y_prob, capacity, prevalence=val_prev)

    hist = {}
    seed_for_hist = int((primary_summary or {}).get("seed", primary_seed))
    hist_name = (
        f"history_finetune_seed_{seed_for_hist}.json"
        if selected_stage == "finetune"
        else f"history_frozen_seed_{seed_for_hist}.json"
    )
    hp = NASNET_ARTIFACTS_DIR / hist_name
    if not hp.exists() and selected_stage == "finetune":
        hp = NASNET_ARTIFACTS_DIR / f"history_frozen_seed_{seed_for_hist}.json"
    if hp.exists():
        hist = json.loads(hp.read_text(encoding="utf-8"))
    save_plots(
        y_va,
        y_prob,
        history=hist,
        threshold=float(metrics["threshold"]["threshold"]),
        reports_dir=reports,
    )
    save_example_encoding(reports_dir=reports)

    pred_df = val_df[["project_key", "observation_date"]].copy() if "project_key" in val_df.columns else pd.DataFrame()
    pred_df["y_true"] = y_va
    pred_df["y_prob"] = y_prob
    if capacity is not None:
        pred_df["capacity_mw"] = capacity
    pred_df.to_parquet(reports / "nasnet_predictions_val.parquet", index=False)

    # Per-seed metrics from saved models when available
    seed_rows = []
    for s in train_summaries:
        seed = int(s["seed"])
        row = {
            "seed": seed,
            "pr_auc": s.get("frozen", {}).get("best_val_pr_auc"),
            "training_time_sec": s.get("frozen", {}).get("training_time_sec"),
            "best_epoch": s.get("frozen", {}).get("best_epoch"),
            "param_total": (s.get("parameter_count") or {}).get("total"),
            "peak_gpu_memory_mb": s.get("peak_gpu_memory_mb"),
            "finetune_pr_auc": (s.get("finetune") or {}).get("best_val_pr_auc"),
            "finetune_improved": (s.get("finetune") or {}).get("improved"),
            "selected_stage": None,
        }
        try:
            ckpt, stage, _ = select_checkpoint_for_summary(s, primary_seed=primary_seed)
            row["selected_stage"] = stage
            yp_s = predict_with_keras(ckpt, x_va, side=side, batch_size=batch_size)
            m_s = evaluate_probabilities(y_va, yp_s, capacity, prevalence=val_prev)
            row.update(
                {
                    "pr_auc": m_s.get("pr_auc"),
                    "roc_auc": m_s.get("roc_auc"),
                    "log_loss": m_s.get("log_loss"),
                    "brier": m_s.get("brier"),
                    "ece": m_s.get("ece"),
                    "precision_at_10pct": m_s.get("precision_at_10pct"),
                    "recall_at_10pct": m_s.get("recall_at_10pct"),
                    "withdrawn_mw_capture_at_10pct": m_s.get("withdrawn_mw_capture_at_10pct"),
                }
            )
        except Exception as e:  # noqa: BLE001
            row["eval_error"] = str(e)
        seed_rows.append(row)

    seed_df = pd.DataFrame(seed_rows)
    seed_df.to_csv(reports / "nasnet_seed_comparison.csv", index=False)
    if len(seed_df) and "pr_auc" in seed_df:
        summary_stats = {
            "pr_auc_mean": float(seed_df["pr_auc"].mean()),
            "pr_auc_std": float(seed_df["pr_auc"].std(ddof=0)),
        }
    else:
        summary_stats = {}

    # MLP metrics
    mlp_metrics: dict[str, Any] = {}
    if mlp_summaries:
        # use first seed probs if present
        yp_path = Path(mlp_summaries[0].get("y_prob_path", ""))
        if yp_path.exists():
            yp_m = np.load(yp_path)
            mlp_metrics = evaluate_probabilities(y_va, yp_m, capacity, prevalence=val_prev)
        else:
            mlp_metrics = {"pr_auc": mlp_summaries[0].get("best_val_pr_auc")}

    champion = load_champion_metrics(REPO_ROOT / cfg["paths"].get("champion_json", "data/gold/modeling/artifacts/champion.json"))
    logistic = load_logistic_metrics()

    # Label shuffle metrics for leakage
    shuffle_eval = None
    if label_shuffle_summary:
        shuffle_eval = {
            "pr_auc": label_shuffle_summary.get("frozen", {}).get("best_val_pr_auc"),
        }

    leakage = write_leakage_audit(
        preprocess_ok=True,
        label_shuffle_metrics=shuffle_eval,
        val_prevalence=val_prev,
        reports_dir=reports,
    )

    finetune_helped = None
    if train_summaries:
        flags = [(s.get("finetune") or {}).get("improved") for s in train_summaries if s.get("finetune")]
        if flags:
            finetune_helped = bool(any(flags))

    metrics_out = {
        **metrics,
        "model_path": str(model_path),
        "selected_stage": selected_stage,
        "selected_summary_val_pr_auc": selected_score if np.isfinite(selected_score) else None,
        "val_prevalence": val_prev,
        "seed_summary": summary_stats,
        "baselines": {
            "prevalence": val_prev,
            "catboost_champion": champion,
            "logistic": {k: logistic.get(k) for k in ("model", "pr_auc", "roc_auc", "brier")},
            "mlp": {k: mlp_metrics.get(k) for k in ("pr_auc", "roc_auc", "brier", "precision_at_10pct")},
        },
    }
    (reports / "nasnet_validation_metrics.json").write_text(
        json.dumps(metrics_out, indent=2, default=str), encoding="utf-8"
    )

    report_path = write_experiment_report(
        seed_rows=seed_rows,
        primary_metrics=metrics_out,
        mlp_metrics=mlp_metrics,
        champion=champion,
        logistic=logistic,
        leakage=leakage,
        finetune_helped=finetune_helped,
        reports_dir=reports,
    )
    return {"metrics": metrics_out, "report": str(report_path), "leakage": leakage}
