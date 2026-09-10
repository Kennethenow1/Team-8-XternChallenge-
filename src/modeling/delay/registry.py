"""Delay matrix loaders. Never reads withdraw_next_12m."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.delay_feature_policy import META, NATIVE_CATEGORICALS

DELAY_MODELING = GOLD_DIR / "delay" / "modeling"
Y_COL = "cod_slip_months_next_12m"
BIN_COL = "cod_slip_ge_12m"


def matrix_path(prefix: str, split: str) -> Path:
    return DELAY_MODELING / f"{prefix}_{split}.parquet"


def load_xy(prefix: str, split: str) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    path = matrix_path(prefix, split)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_parquet(path)
    meta_cols = [c for c in META if c in df.columns]
    y = pd.to_numeric(df[Y_COL], errors="coerce") if Y_COL in df.columns else pd.Series([np.nan] * len(df))
    X = df.drop(columns=[c for c in META if c in df.columns], errors="ignore")
    meta = df[meta_cols].copy() if meta_cols else pd.DataFrame(index=df.index)
    return X, y, meta


def load_seq(split: str) -> dict[str, Any]:
    path = DELAY_MODELING / f"delay_seq_v1_{split}.npz"
    if not path.exists():
        raise FileNotFoundError(path)
    z = np.load(path, allow_pickle=True)
    return {k: z[k] for k in z.files}


def y_binary(meta: pd.DataFrame) -> pd.Series:
    if BIN_COL in meta.columns:
        return pd.to_numeric(meta[BIN_COL], errors="coerce")
    y = pd.to_numeric(meta.get(Y_COL), errors="coerce")
    return (y >= 12).astype("float64")


def capacity(meta: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(meta["capacity_mw"], errors="coerce") if "capacity_mw" in meta.columns else pd.Series(np.nan, index=meta.index)


def gia_mask(meta: pd.DataFrame) -> np.ndarray:
    if "is_gia" in meta.columns:
        return meta["is_gia"].fillna(False).astype(bool).to_numpy()
    return np.zeros(len(meta), dtype=bool)
