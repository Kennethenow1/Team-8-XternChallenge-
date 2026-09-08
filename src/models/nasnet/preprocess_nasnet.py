"""TRAIN-only preprocessing for NASNet tabular-to-image experiment."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.preprocessing import StandardScaler

from src.common.paths import REPO_ROOT
from src.modeling.feature_analysis import _classify_model_ready_column
from src.models.nasnet import (
    FEATURE_ROLES_X,
    META_EXCLUDE,
    MODEL_READY_TRAIN,
    MODEL_READY_VAL,
    NASNET_ARTIFACTS_DIR,
    NASNET_DATA_DIR,
    TARGET_CANDIDATES,
    assert_not_sealed_path,
    ensure_nasnet_dirs,
)


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (REPO_ROOT / "configs" / "nasnetlarge.yaml")
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_target_column(columns: list[str]) -> str:
    hits = [c for c in TARGET_CANDIDATES if c in columns]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise RuntimeError(
            "No binary 12-month withdrawal label found. "
            f"Looked for {TARGET_CANDIDATES} among columns."
        )
    raise RuntimeError(
        f"Multiple possible target columns found: {hits}. "
        "Refuse to guess — resolve to a single label."
    )


def _load_schema_roles(schema_csv: Path, train: pd.DataFrame) -> dict[str, str]:
    """Prefer live TRAIN classification; cross-check schema CSV when present."""
    live = {_classify_model_ready_column(c, train[c])["role"]: None for c in train.columns}
    # rebuild properly
    roles = {c: _classify_model_ready_column(c, train[c])["role"] for c in train.columns}
    if schema_csv.exists():
        schema = pd.read_csv(schema_csv)
        if {"feature", "role"}.issubset(schema.columns):
            for _, row in schema.iterrows():
                feat = str(row["feature"])
                if feat in roles and roles[feat] != str(row["role"]):
                    # Prefer live TRAIN classification for binary vs numeric edge cases
                    pass
    return roles


def build_feature_roles(
    train: pd.DataFrame,
    *,
    target: str,
    schema_csv: Path | None = None,
) -> dict[str, Any]:
    roles = {
        c: _classify_model_ready_column(c, train[c])["role"]
        for c in train.columns
    }
    feature_cols: list[str] = []
    role_map: dict[str, str] = {}
    excluded: dict[str, str] = {}
    for c, role in roles.items():
        if c == target or c in META_EXCLUDE or role in {"label", "identifier", "time_key"}:
            excluded[c] = role if c != target else "label"
            continue
        if role == "categorical":
            raise RuntimeError(f"Unexpected non-numeric categorical column in model-ready: {c}")
        if role not in FEATURE_ROLES_X:
            excluded[c] = role
            continue
        feature_cols.append(c)
        role_map[c] = role
    return {
        "target": target,
        "feature_columns": feature_cols,
        "roles": role_map,
        "excluded": excluded,
        "schema_csv": str(schema_csv) if schema_csv else None,
        "n_features": len(feature_cols),
        "side": int(math.ceil(math.sqrt(len(feature_cols)))),
    }


def _train_mode(series: pd.Series) -> float:
    non_null = series.dropna()
    if len(non_null) == 0:
        return 0.0
    modes = non_null.mode()
    return float(modes.iloc[0]) if len(modes) else 0.0


def _validate_binary_column(name: str, series: pd.Series) -> None:
    vals = pd.unique(series.dropna())
    bad = [v for v in vals if float(v) not in (0.0, 1.0)]
    if bad:
        raise RuntimeError(
            f"Column '{name}' marked binary/one-hot/missing-indicator but contains "
            f"non-binary values among non-missing: {bad[:10]}"
        )


def fit_transform_features(
    train: pd.DataFrame,
    val: pd.DataFrame,
    feature_meta: dict[str, Any],
    *,
    low_pct: float = 0.5,
    high_pct: float = 99.5,
    z_clip: float = 5.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Fit preprocess on TRAIN only; transform TRAIN and VAL."""
    cols = feature_meta["feature_columns"]
    roles: dict[str, str] = feature_meta["roles"]
    if list(train[cols].columns) != cols or list(val[cols].columns) != cols:
        raise RuntimeError("TRAIN/VAL feature columns missing or order mismatch")

    X_tr = train[cols].copy()
    X_va = val[cols].copy()
    for c in cols:
        X_tr[c] = pd.to_numeric(X_tr[c], errors="coerce")
        X_va[c] = pd.to_numeric(X_va[c], errors="coerce")

    numeric_cols = [c for c in cols if roles[c] == "numeric"]
    binary_cols = [c for c in cols if roles[c] in {"binary", "onehot", "missing_indicator"}]

    medians: dict[str, float] = {}
    clip_bounds: dict[str, dict[str, float]] = {}
    binary_modes: dict[str, float] = {}

    # Continuous
    for c in numeric_cols:
        X_tr[c] = X_tr[c].replace([np.inf, -np.inf], np.nan)
        X_va[c] = X_va[c].replace([np.inf, -np.inf], np.nan)
        med = float(X_tr[c].median(skipna=True))
        if not np.isfinite(med):
            med = 0.0
        medians[c] = med
        X_tr[c] = X_tr[c].fillna(med)
        X_va[c] = X_va[c].fillna(med)
        lo = float(np.nanpercentile(X_tr[c].to_numpy(dtype=float), low_pct))
        hi = float(np.nanpercentile(X_tr[c].to_numpy(dtype=float), high_pct))
        if not np.isfinite(lo):
            lo = float(X_tr[c].min())
        if not np.isfinite(hi):
            hi = float(X_tr[c].max())
        if lo > hi:
            lo, hi = hi, lo
        clip_bounds[c] = {"low": lo, "high": hi}
        X_tr[c] = X_tr[c].clip(lo, hi)
        X_va[c] = X_va[c].clip(lo, hi)

    scaler = StandardScaler()
    if numeric_cols:
        X_tr[numeric_cols] = scaler.fit_transform(X_tr[numeric_cols])
        X_va[numeric_cols] = scaler.transform(X_va[numeric_cols])
        X_tr[numeric_cols] = np.clip(X_tr[numeric_cols].to_numpy(dtype=float), -z_clip, z_clip) / z_clip
        X_va[numeric_cols] = np.clip(X_va[numeric_cols].to_numpy(dtype=float), -z_clip, z_clip) / z_clip

    # Binary / one-hot / missing indicators
    for c in binary_cols:
        _validate_binary_column(c, X_tr[c])
        _validate_binary_column(c, X_va[c])
        mode = _train_mode(X_tr[c])
        if mode not in (0.0, 1.0):
            mode = 0.0
        binary_modes[c] = mode
        X_tr[c] = X_tr[c].fillna(mode)
        X_va[c] = X_va[c].fillna(mode)
        # after fill must be 0/1
        _validate_binary_column(c, X_tr[c])
        _validate_binary_column(c, X_va[c])
        X_tr[c] = X_tr[c].astype(float) * 2.0 - 1.0
        X_va[c] = X_va[c].astype(float) * 2.0 - 1.0

    # Reassemble in frozen order
    out_tr = X_tr[cols].astype(np.float32)
    out_va = X_va[cols].astype(np.float32)
    _assert_normalized(out_tr, "TRAIN")
    _assert_normalized(out_va, "VAL")

    artifacts = {
        "numeric_medians": medians,
        "numeric_clip_bounds": clip_bounds,
        "binary_modes": binary_modes,
        "scaler": scaler,
        "numeric_cols": numeric_cols,
        "binary_cols": binary_cols,
        "z_clip": z_clip,
    }
    return out_tr, out_va, artifacts


def _assert_normalized(df: pd.DataFrame, name: str) -> None:
    arr = df.to_numpy(dtype=float)
    if not np.isfinite(arr).all():
        raise RuntimeError(f"{name} features contain NaN or infinity after preprocessing")
    mn, mx = float(np.min(arr)), float(np.max(arr))
    if mn < -1.0 - 1e-6 or mx > 1.0 + 1e-6:
        raise RuntimeError(f"{name} features out of [-1,1]: min={mn}, max={mx}")


def build_pixel_map(feature_meta: dict[str, Any]) -> list[dict[str, Any]]:
    cols = feature_meta["feature_columns"]
    roles = feature_meta["roles"]
    side = int(feature_meta["side"])
    rows: list[dict[str, Any]] = []
    for i in range(side * side):
        r, c = divmod(i, side)
        if i < len(cols):
            name = cols[i]
            rows.append(
                {
                    "feature_name": name,
                    "feature_role": roles[name],
                    "feature_index": i,
                    "grid_row": r,
                    "grid_column": c,
                    "is_padding": False,
                }
            )
        else:
            rows.append(
                {
                    "feature_name": None,
                    "feature_role": "padding",
                    "feature_index": i,
                    "grid_row": r,
                    "grid_column": c,
                    "is_padding": True,
                }
            )
    return rows


def _assert_same_feature_order(train: pd.DataFrame, val: pd.DataFrame, cols: list[str]) -> None:
    if list(train.columns) != list(val.columns):
        raise RuntimeError("TRAIN and VAL do not share the same columns")
    missing_tr = [c for c in cols if c not in train.columns]
    missing_va = [c for c in cols if c not in val.columns]
    if missing_tr or missing_va:
        raise RuntimeError(f"Missing features train={missing_tr} val={missing_va}")


def run_preprocess(*, config: dict[str, Any] | None = None, save: bool = True) -> dict[str, Any]:
    cfg = config or load_config()
    ensure_nasnet_dirs()

    train_path = REPO_ROOT / cfg["paths"]["model_ready_train"]
    val_path = REPO_ROOT / cfg["paths"]["model_ready_val"]
    assert_not_sealed_path(train_path)
    assert_not_sealed_path(val_path)
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError(f"Missing model_ready train/val: {train_path} / {val_path}")

    train = pd.read_parquet(train_path)
    val = pd.read_parquet(val_path)
    target = resolve_target_column(list(train.columns))
    if target not in val.columns:
        raise RuntimeError(f"VAL missing target column {target}")

    schema_csv = REPO_ROOT / cfg["paths"].get(
        "schema_csv", "data/quality_reports/modeling/model_ready_schema.csv"
    )
    feature_meta = build_feature_roles(train, target=target, schema_csv=schema_csv)
    cols = feature_meta["feature_columns"]
    _assert_same_feature_order(train, val, cols)
    if list(val[cols].columns) != cols:
        raise RuntimeError("VAL feature order does not match TRAIN frozen order")

    prep_cfg = cfg.get("preprocess", {})
    X_tr, X_va, prep_art = fit_transform_features(
        train,
        val,
        feature_meta,
        low_pct=float(prep_cfg.get("numeric_low_pct", 0.5)),
        high_pct=float(prep_cfg.get("numeric_high_pct", 99.5)),
        z_clip=float(prep_cfg.get("z_clip", 5.0)),
    )

    pixel_map = build_pixel_map(feature_meta)

    keep_meta = ["project_key", "observation_date"]
    raw_cap_tr = (
        pd.to_numeric(train["capacity_mw"], errors="coerce") if "capacity_mw" in train.columns else None
    )
    raw_cap_va = (
        pd.to_numeric(val["capacity_mw"], errors="coerce") if "capacity_mw" in val.columns else None
    )

    def _sanitize_raw_mw(series: pd.Series) -> pd.Series:
        """Ops capacity: keep positive MW only; non-positive / non-finite → NaN."""
        out = pd.to_numeric(series, errors="coerce").astype(float)
        out = out.where(out > 0.0)
        return out

    ready_tr = train[keep_meta].copy()
    ready_tr[cols] = X_tr
    ready_tr[target] = pd.to_numeric(train[target], errors="coerce").astype(int)
    if raw_cap_tr is not None:
        # Keep raw MW for ops metrics; feature block may also contain scaled capacity_mw
        ready_tr["capacity_mw_raw"] = _sanitize_raw_mw(raw_cap_tr)

    ready_va = val[keep_meta].copy()
    ready_va[cols] = X_va
    ready_va[target] = pd.to_numeric(val[target], errors="coerce").astype(int)
    if raw_cap_va is not None:
        ready_va["capacity_mw_raw"] = _sanitize_raw_mw(raw_cap_va)

    # Validate no target/ids among feature block
    for bad in META_EXCLUDE | {target}:
        if bad in cols:
            raise RuntimeError(f"Forbidden column leaked into features: {bad}")

    out: dict[str, Any] = {
        "target": target,
        "n_train": int(len(ready_tr)),
        "n_val": int(len(ready_va)),
        "n_features": len(cols),
        "side": feature_meta["side"],
        "train_prevalence": float(ready_tr[target].mean()),
        "val_prevalence": float(ready_va[target].mean()),
        "feature_meta": feature_meta,
        "paths": {},
    }

    if save:
        art = NASNET_ARTIFACTS_DIR
        data = NASNET_DATA_DIR
        art.mkdir(parents=True, exist_ok=True)
        data.mkdir(parents=True, exist_ok=True)

        roles_path = art / "nasnet_feature_roles.json"
        order_path = art / "nasnet_feature_order.json"
        med_path = art / "numeric_medians.json"
        clip_path = art / "numeric_clip_bounds.json"
        scaler_path = art / "numeric_scaler.joblib"
        pixel_path = art / "nasnet_feature_pixel_map.json"
        train_out = data / "nasnet_ready_train.parquet"
        val_out = data / "nasnet_ready_val.parquet"

        roles_path.write_text(json.dumps(feature_meta, indent=2), encoding="utf-8")
        order_path.write_text(json.dumps({"feature_columns": cols}, indent=2), encoding="utf-8")
        med_path.write_text(json.dumps(prep_art["numeric_medians"], indent=2), encoding="utf-8")
        clip_path.write_text(json.dumps(prep_art["numeric_clip_bounds"], indent=2), encoding="utf-8")
        joblib.dump(
            {
                "scaler": prep_art["scaler"],
                "numeric_cols": prep_art["numeric_cols"],
                "binary_modes": prep_art["binary_modes"],
                "z_clip": prep_art["z_clip"],
            },
            scaler_path,
        )
        pixel_path.write_text(json.dumps(pixel_map, indent=2), encoding="utf-8")
        ready_tr.to_parquet(train_out, index=False)
        ready_va.to_parquet(val_out, index=False)

        out["paths"] = {
            "roles": str(roles_path),
            "order": str(order_path),
            "medians": str(med_path),
            "clip_bounds": str(clip_path),
            "scaler": str(scaler_path),
            "pixel_map": str(pixel_path),
            "ready_train": str(train_out),
            "ready_val": str(val_out),
        }
    return out


def load_ready_matrices(
    *,
    data_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], str]:
    data = data_dir or NASNET_DATA_DIR
    art = artifacts_dir or NASNET_ARTIFACTS_DIR
    train = pd.read_parquet(data / "nasnet_ready_train.parquet")
    val = pd.read_parquet(data / "nasnet_ready_val.parquet")
    order = json.loads((art / "nasnet_feature_order.json").read_text(encoding="utf-8"))
    cols = list(order["feature_columns"])
    roles = json.loads((art / "nasnet_feature_roles.json").read_text(encoding="utf-8"))
    target = roles["target"]
    return train, val, cols, target
