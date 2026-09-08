"""Model ↔ matrix routing and artifact directory layout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.feature_policy import META
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS

MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_DIR = MODELING_DIR / "artifacts"

# name -> matrix prefix
MODEL_MATRIX = {
    "constant": "logistic_v1",  # only needs labels / prevalence
    "logistic_l2": "logistic_v1",
    "logistic_elasticnet": "logistic_v1",
    "catboost": "catboost_native_v1",
    "lightgbm": "tree_v1",
    "xgboost": "tree_v1",
    "tabicl": "foundation_v1",
    "tabpfn": "foundation_v1",
    "tabm": "tabm_v1",
    "ft_transformer": "ftt_v1",
}


def ensure_artifact_dirs() -> dict[str, Path]:
    dirs = {
        "root": ARTIFACTS_DIR,
        "preprocessing": ARTIFACTS_DIR / "preprocessing",
        "models": ARTIFACTS_DIR / "models",
        "predictions": ARTIFACTS_DIR / "predictions",
        "metrics": ARTIFACTS_DIR / "metrics",
        "features": ARTIFACTS_DIR / "features",
        "hpo": ARTIFACTS_DIR / "hpo",
        "calibration": ARTIFACTS_DIR / "calibration",
    }
    for name in MODEL_MATRIX:
        if name == "constant":
            continue
        dirs[f"model_{name}"] = dirs["models"] / name
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def matrix_path(prefix: str, split: str) -> Path:
    return MODELING_DIR / f"{prefix}_{split}.parquet"


def load_xy(prefix: str, split: str) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    path = matrix_path(prefix, split)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    meta = df[[c for c in ("project_key", "observation_date") if c in df.columns]].copy()
    y = df["withdraw_next_12m"] if "withdraw_next_12m" in df.columns else pd.Series([pd.NA] * len(df))
    X = df.drop(columns=[c for c in META if c in df.columns], errors="ignore")
    return X, y, meta


def load_capacity_mw(meta: pd.DataFrame) -> pd.Series:
    """Join raw capacity_mw from enriched panel onto matrix meta keys."""
    panel_path = GOLD_DIR / "withdrawal_panel_enriched.parquet"
    keys = [c for c in ("project_key", "observation_date") if c in meta.columns]
    if len(keys) < 2 or not panel_path.exists():
        return pd.Series([float("nan")] * len(meta), index=meta.index)
    panel = pd.read_parquet(panel_path, columns=["project_key", "observation_date", "capacity_mw"])
    panel = panel.copy()
    panel["observation_date"] = pd.to_datetime(panel["observation_date"])
    left = meta.copy()
    left["observation_date"] = pd.to_datetime(left["observation_date"])
    merged = left.merge(panel, on=["project_key", "observation_date"], how="left")
    col = "capacity_mw"
    if col not in merged.columns:
        for c in merged.columns:
            if c.startswith("capacity_mw"):
                col = c
                break
    if col not in merged.columns:
        return pd.Series([float("nan")] * len(meta), index=meta.index)
    return pd.to_numeric(merged[col], errors="coerce")


def feature_list_from_X(X: pd.DataFrame) -> dict[str, Any]:
    cats = [c for c in NATIVE_CATEGORICALS if c in X.columns]
    return {
        "feature_columns": list(X.columns),
        "categorical_columns": cats,
        "n": len(X.columns),
    }


def model_dir(name: str) -> Path:
    ensure_artifact_dirs()
    return ARTIFACTS_DIR / "models" / name


def save_run_artifacts(
    name: str,
    *,
    hyperparams: dict[str, Any],
    feature_list: dict[str, Any],
    train_metadata: dict[str, Any],
    metrics: dict[str, Any],
    val_predictions: pd.DataFrame | None = None,
    model_obj: Any = None,
    model_filename: str = "model.joblib",
) -> Path:
    import joblib

    d = model_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "hyperparameters.json").write_text(json.dumps(hyperparams, indent=2, default=str), encoding="utf-8")
    (d / "feature_list.json").write_text(json.dumps(feature_list, indent=2), encoding="utf-8")
    (d / "train_metadata.json").write_text(json.dumps(train_metadata, indent=2, default=str), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    if val_predictions is not None:
        pred_dir = ARTIFACTS_DIR / "predictions" / name
        pred_dir.mkdir(parents=True, exist_ok=True)
        val_predictions.to_parquet(pred_dir / "val_predictions.parquet", index=False)
        # also under model dir for convenience
        val_predictions.to_parquet(d / "val_predictions.parquet", index=False)
    if model_obj is not None:
        joblib.dump(model_obj, d / model_filename)
    return d
