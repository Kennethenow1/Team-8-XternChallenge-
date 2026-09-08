"""Label/followup and train→val feature drift audits (read-only on Gold)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.common.paths import GOLD_DIR
from src.modeling.feature_policy import MACRO_FAMILY
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.model_registry import ensure_artifact_dirs, load_xy, matrix_path

PANEL_PATH = GOLD_DIR / "withdrawal_panel_enriched.parquet"
MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_METRICS = MODELING_DIR / "artifacts" / "metrics"


def label_followup_audit() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH)
    panel["observation_date"] = pd.to_datetime(panel["observation_date"])
    panel["year"] = panel["observation_date"].dt.year
    g = (
        panel.groupby(["split", "year"], dropna=False)
        .agg(
            n=("project_key", "size"),
            withdrawals=("withdraw_next_12m", "sum"),
            withdrawal_rate=("withdraw_next_12m", "mean"),
            complete_followup_rate=("complete_followup", "mean"),
        )
        .reset_index()
    )
    return g.sort_values(["split", "year"])


def write_label_followup_audit(metrics_dir: Path | None = None) -> Path:
    metrics_dir = metrics_dir or ARTIFACTS_METRICS
    metrics_dir.mkdir(parents=True, exist_ok=True)
    tbl = label_followup_audit()
    csv_path = metrics_dir / "label_followup_audit.csv"
    md_path = metrics_dir / "label_followup_audit.md"
    tbl.to_csv(csv_path, index=False)

    # Modeling matrix counts
    mat_lines = []
    for split in ("train", "val", "test", "score"):
        p = matrix_path("catboost_native_v1", split)
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        y = pd.to_numeric(df.get("withdraw_next_12m"), errors="coerce")
        mat_lines.append(
            f"- `{split}` matrix rows={len(df)}, positives={int(y.fillna(0).sum())}, "
            f"rate={float(y.mean()) if y.notna().any() else float('nan'):.4f}"
        )

    val = tbl[(tbl["split"] == "val")]
    val_fu = float(val["complete_followup_rate"].mean()) if len(val) else float("nan")
    lines = [
        "# Label / follow-up audit",
        "",
        "Do **not** rebalance validation — keep the real future prevalence.",
        "",
        "## Panel by split × year",
        "",
        "| " + " | ".join(tbl.columns.astype(str)) + " |",
        "| " + " | ".join(["---"] * len(tbl.columns)) + " |",
    ]
    for _, r in tbl.iterrows():
        lines.append(
            "| "
            + " | ".join(
                f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c]) for c in tbl.columns
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Modeling matrices (`catboost_native_v1`)",
            "",
            *mat_lines,
            "",
            "## 12-month follow-up on validation",
            "",
            f"- Panel val `complete_followup` rate ≈ **{val_fu:.4f}**",
            "- Rows with `complete_followup=True` are the supervised evaluation population "
            "(≥12 months of outcome visibility by construction of the label).",
            "- Modeling val/test matrices are filtered to complete follow-up in feature engineering.",
            "",
            f"CSV: `{csv_path}`",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def feature_drift_train_val(prefix: str = "catboost_native_v1") -> tuple[pd.DataFrame, pd.DataFrame]:
    X_tr, _, _ = load_xy(prefix, "train")
    X_va, _, _ = load_xy(prefix, "val")
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    num_cols = [c for c in X_tr.columns if c not in cat_cols]

    num_rows = []
    for c in num_cols:
        a = pd.to_numeric(X_tr[c], errors="coerce")
        b = pd.to_numeric(X_va[c], errors="coerce")
        a_nn, b_nn = a.dropna(), b.dropna()
        if len(a_nn) < 30 or len(b_nn) < 30:
            ks, pval = float("nan"), float("nan")
            smd = float("nan")
        else:
            ks, pval = stats.ks_2samp(a_nn, b_nn)
            pooled = np.sqrt(0.5 * (a_nn.var() + b_nn.var()))
            smd = float((b_nn.mean() - a_nn.mean()) / pooled) if pooled > 0 else float("nan")
        num_rows.append(
            {
                "feature": c,
                "family": "macro" if c in MACRO_FAMILY else "other",
                "train_mean": float(a_nn.mean()) if len(a_nn) else float("nan"),
                "val_mean": float(b_nn.mean()) if len(b_nn) else float("nan"),
                "train_std": float(a_nn.std()) if len(a_nn) else float("nan"),
                "val_std": float(b_nn.std()) if len(b_nn) else float("nan"),
                "smd_val_minus_train": smd,
                "ks_stat": float(ks),
                "ks_pvalue": float(pval),
                "train_nunique": int(a_nn.nunique()),
                "val_nunique": int(b_nn.nunique()),
            }
        )
    num_df = pd.DataFrame(num_rows).sort_values("ks_stat", ascending=False)

    cat_rows = []
    for c in cat_cols:
        a = X_tr[c].astype("string").fillna("__MISSING__")
        b = X_va[c].astype("string").fillna("__MISSING__")
        pa = a.value_counts(normalize=True)
        pb = b.value_counts(normalize=True)
        levels = sorted(set(pa.index) | set(pb.index))
        for lev in levels:
            cat_rows.append(
                {
                    "feature": c,
                    "level": lev,
                    "train_share": float(pa.get(lev, 0.0)),
                    "val_share": float(pb.get(lev, 0.0)),
                    "share_delta": float(pb.get(lev, 0.0) - pa.get(lev, 0.0)),
                }
            )
    cat_df = pd.DataFrame(cat_rows).sort_values("share_delta", key=lambda s: s.abs(), ascending=False)
    return num_df, cat_df


def write_feature_drift_report(metrics_dir: Path | None = None) -> Path:
    metrics_dir = metrics_dir or ARTIFACTS_METRICS
    metrics_dir.mkdir(parents=True, exist_ok=True)
    num_df, cat_df = feature_drift_train_val()
    num_csv = metrics_dir / "feature_drift_train_val_numeric.csv"
    cat_csv = metrics_dir / "feature_drift_train_val_categorical.csv"
    md_path = metrics_dir / "feature_drift_train_val.md"
    num_df.to_csv(num_csv, index=False)
    cat_df.to_csv(cat_csv, index=False)

    macros = num_df[num_df["family"] == "macro"].head(20)
    top = num_df.head(15)
    lines = [
        "# Train → validation feature drift",
        "",
        "Computed on `catboost_native_v1` (same semantics as foundation_v1).",
        "",
        "## Year-grain / macro family (ablation candidates)",
        "",
        "These include FRED/EIA macros and system-wide `prior_12m_*` signals.",
        "",
        "| feature | train_nunique | val_nunique | smd | ks |",
        "|---------|---------------|-------------|-----|----|",
    ]
    for _, r in macros.iterrows():
        lines.append(
            f"| `{r['feature']}` | {r['train_nunique']} | {r['val_nunique']} | "
            f"{r['smd_val_minus_train']:.3f} | {r['ks_stat']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Top numeric drift by KS",
            "",
            "| feature | smd | ks | train_mean | val_mean |",
            "|---------|-----|----|------------|----------|",
        ]
    )
    for _, r in top.iterrows():
        lines.append(
            f"| `{r['feature']}` | {r['smd_val_minus_train']:.3f} | {r['ks_stat']:.3f} | "
            f"{r['train_mean']:.4g} | {r['val_mean']:.4g} |"
        )
    lines.extend(
        [
            "",
            "## Largest categorical share shifts",
            "",
            "| feature | level | train_share | val_share | delta |",
            "|---------|-------|-------------|-----------|-------|",
        ]
    )
    for _, r in cat_df.head(20).iterrows():
        lines.append(
            f"| `{r['feature']}` | {r['level']} | {r['train_share']:.3f} | "
            f"{r['val_share']:.3f} | {r['share_delta']:+.3f} |"
        )
    lines.extend(["", f"CSVs: `{num_csv}`, `{cat_csv}`", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def run_all_audits() -> dict[str, str]:
    ensure_artifact_dirs()
    return {
        "label_followup": str(write_label_followup_audit()),
        "feature_drift": str(write_feature_drift_report()),
    }
