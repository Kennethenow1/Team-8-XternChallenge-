"""CatBoost-native and TabM matrix builders from foundation_v1 semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from src.common.paths import GOLD_DIR
from src.modeling.feature_policy import META
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS, SPLITS, foundation_column_lists

MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_DIR = MODELING_DIR / "artifacts"
PREPROC_DIR = ARTIFACTS_DIR / "preprocessing"


def write_catboost_native_matrices(
    modeling_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """Materialize catboost_native_v1_* from foundation_v1_* (native categoricals)."""
    modeling_dir = modeling_dir or MODELING_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    feature_cols: list[str] | None = None
    for split in SPLITS:
        src = modeling_dir / f"foundation_v1_{split}.parquet"
        if not src.exists():
            continue
        df = pd.read_parquet(src)
        for cat in NATIVE_CATEGORICALS:
            if cat in df.columns:
                # pandas categorical for CatBoost cat_features detection
                df[cat] = df[cat].astype("string").astype("category")
        out = modeling_dir / f"catboost_native_v1_{split}.parquet"
        df.to_parquet(out, index=False)
        paths[split] = str(out)
        if split == "train":
            feature_cols = [c for c in df.columns if c not in META]

    assert feature_cols is not None
    col_lists = foundation_column_lists(feature_cols)
    cols_path = artifacts_dir / "feature_columns_catboost_native_v1.json"
    cols_path.write_text(
        json.dumps(
            {
                **col_lists,
                "n": len(feature_cols),
                "policy": "catboost_native_v1",
                "notes": [
                    "Same semantics as foundation_v1; categoricals stored as pandas category.",
                    "Numeric NaNs retained; no scaling / one-hot.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "paths": paths,
        "n_features": len(feature_cols),
        "feature_columns_path": str(cols_path),
        "categorical_columns": col_lists["categorical_columns"],
    }


def _fit_category_maps(train: pd.DataFrame, cat_cols: list[str]) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for c in cat_cols:
        vals = train[c].astype("string").fillna("__MISSING__")
        uniq = sorted(vals.unique().tolist())
        maps[c] = {v: i for i, v in enumerate(uniq)}
        # reserve max+1 for unseen
    return maps


def _encode_cats(df: pd.DataFrame, cat_cols: list[str], maps: dict[str, dict[str, int]]) -> pd.DataFrame:
    out = df.copy()
    for c in cat_cols:
        m = maps[c]
        unseen = max(m.values()) + 1 if m else 0
        s = out[c].astype("string").fillna("__MISSING__")
        out[c] = s.map(lambda x, _m=m, _u=unseen: _m.get(x, _u)).astype(np.int32)
    return out


def run_tabm_matrices(
    modeling_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """Build tabm_v1_*: integer cats, train-median numeric impute, train StandardScaler."""
    modeling_dir = modeling_dir or MODELING_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    preproc_dir = artifacts_dir / "preprocessing"
    preproc_dir.mkdir(parents=True, exist_ok=True)

    train_src = modeling_dir / "foundation_v1_train.parquet"
    if not train_src.exists():
        raise FileNotFoundError(train_src)

    train = pd.read_parquet(train_src)
    feature_cols = [c for c in train.columns if c not in META]
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in feature_cols]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    cat_maps = _fit_category_maps(train, cat_cols)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()

    train_enc = _encode_cats(train, cat_cols, cat_maps)
    X_num = imputer.fit_transform(train_enc[num_cols].apply(pd.to_numeric, errors="coerce"))
    X_num = scaler.fit_transform(X_num)

    joblib.dump(
        {
            "cat_maps": cat_maps,
            "imputer": imputer,
            "scaler": scaler,
            "numeric_columns": num_cols,
            "categorical_columns": cat_cols,
            "feature_columns": cat_cols + num_cols,
        },
        preproc_dir / "tabm_transformers.joblib",
    )

    paths: dict[str, str] = {}
    for split in SPLITS:
        src = modeling_dir / f"foundation_v1_{split}.parquet"
        if not src.exists():
            continue
        df = pd.read_parquet(src)
        meta = [c for c in ("project_key", "observation_date", "withdraw_next_12m") if c in df.columns]
        enc = _encode_cats(df, cat_cols, cat_maps)
        Xn = imputer.transform(enc[num_cols].apply(pd.to_numeric, errors="coerce"))
        Xn = scaler.transform(Xn)
        out = enc[meta].copy()
        for i, c in enumerate(cat_cols):
            out[c] = enc[c].to_numpy()
        for i, c in enumerate(num_cols):
            out[c] = Xn[:, i]
        # column order: meta + cats + nums
        ordered = meta + cat_cols + num_cols
        out = out[ordered]
        path = modeling_dir / f"tabm_v1_{split}.parquet"
        out.to_parquet(path, index=False)
        paths[split] = str(path)

    cols_path = artifacts_dir / "feature_columns_tabm_v1.json"
    cols_path.write_text(
        json.dumps(
            {
                "feature_columns": cat_cols + num_cols,
                "categorical_columns": cat_cols,
                "numeric_columns": num_cols,
                "n": len(cat_cols) + len(num_cols),
                "policy": "tabm_v1",
                "notes": [
                    "Categoricals → integer IDs (train vocabulary; unseen → max+1).",
                    "Numeric: train-median impute + StandardScaler.",
                    "Missing indicators retained among numeric columns.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "paths": paths,
        "n_features": len(cat_cols) + len(num_cols),
        "feature_columns_path": str(cols_path),
        "categorical_columns": cat_cols,
        "transformers_path": str(preproc_dir / "tabm_transformers.joblib"),
    }


def run_ftt_matrices(
    modeling_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """Emit ftt_v1_* as an alias of tabm_v1 normalize (int cats + median + StandardScaler)."""
    modeling_dir = modeling_dir or MODELING_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR

    # Ensure TabM matrices / transformers exist
    tabm = run_tabm_matrices(modeling_dir, artifacts_dir)

    import shutil

    paths: dict[str, str] = {}
    for split in SPLITS:
        src = modeling_dir / f"tabm_v1_{split}.parquet"
        if not src.exists():
            continue
        dst = modeling_dir / f"ftt_v1_{split}.parquet"
        shutil.copy2(src, dst)
        paths[split] = str(dst)

    tabm_cols_path = Path(tabm["feature_columns_path"])
    tabm_meta = json.loads(tabm_cols_path.read_text(encoding="utf-8"))
    cols_path = artifacts_dir / "feature_columns_ftt_v1.json"
    cols_path.write_text(
        json.dumps(
            {
                "feature_columns": tabm_meta["feature_columns"],
                "categorical_columns": tabm_meta["categorical_columns"],
                "numeric_columns": tabm_meta["numeric_columns"],
                "n": tabm_meta["n"],
                "policy": "ftt_v1 (alias of tabm_v1 normalize)",
                "notes": [
                    "Same encoding as tabm_v1: integer category IDs + train-median + StandardScaler.",
                    "Dedicated prefix for FT-Transformer routing; do not re-fit scalers on val/test.",
                ],
                "alias_of": "tabm_v1",
                "transformers_path": tabm["transformers_path"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Shared preprocess artifact pointer
    preproc_dir = artifacts_dir / "preprocessing"
    preproc_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            **joblib.load(tabm["transformers_path"]),
            "policy": "ftt_v1",
            "alias_of": "tabm_v1",
        },
        preproc_dir / "ftt_transformers.joblib",
    )
    return {
        "paths": paths,
        "n_features": tabm["n_features"],
        "feature_columns_path": str(cols_path),
        "categorical_columns": tabm["categorical_columns"],
        "transformers_path": str(preproc_dir / "ftt_transformers.joblib"),
    }


def run_catboost_and_tabm_matrices(
    modeling_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    cb = write_catboost_native_matrices(modeling_dir, artifacts_dir)
    tabm = run_tabm_matrices(modeling_dir, artifacts_dir)
    ftt = run_ftt_matrices(modeling_dir, artifacts_dir)
    return {"catboost_native": cb, "tabm": tabm, "ftt": ftt}
