"""Shared delay-trainer helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.modeling.delay.registry import capacity, gia_mask, y_binary
from src.modeling.delay_eval_protocol import full_delay_metrics


def labeled_mask(y: pd.Series) -> pd.Series:
    return pd.to_numeric(y, errors="coerce").notna()


def pack_metrics(
    *,
    model: str,
    y_va: pd.Series,
    pred: np.ndarray,
    meta_va: pd.DataFrame,
    history: list[dict[str, float]] | None = None,
    extra: dict[str, Any] | None = None,
    status: str = "ok",
    reason: str | None = None,
) -> dict[str, Any]:
    yb = y_binary(meta_va)
    mw = capacity(meta_va)
    gia = gia_mask(meta_va)
    m = full_delay_metrics(
        y_va,
        pred,
        y_bin=yb,
        score_bin=pred,
        capacity_mw=mw.to_numpy() if mw is not None else None,
        meta=meta_va,
        is_gia=gia,
    )
    m["model"] = model
    m["status"] = status
    if reason:
        m["reason"] = reason
    if history is not None:
        m["history"] = history
        m["_history"] = history
    if extra:
        m.update(extra)
    m["n_features"] = extra.get("n_features") if extra else m.get("n_features")
    m["_y_va"] = np.asarray(pd.to_numeric(y_va, errors="coerce"), dtype=float)
    m["_pred"] = np.asarray(pred, dtype=float).reshape(-1)
    return m


def history_from_evals(train_loss, val_loss, train_mae=None, val_mae=None, val_rmse=None) -> list[dict[str, float]]:
    n = max(len(train_loss or []), len(val_loss or []), 0)
    rows = []
    for i in range(n):
        row: dict[str, float] = {"step": float(i)}
        if train_loss is not None and i < len(train_loss):
            row["train_loss"] = float(train_loss[i])
        if val_loss is not None and i < len(val_loss):
            row["val_loss"] = float(val_loss[i])
        if train_mae is not None and i < len(train_mae):
            row["train_mae"] = float(train_mae[i])
        if val_mae is not None and i < len(val_mae):
            row["val_mae"] = float(val_mae[i])
        if val_rmse is not None and i < len(val_rmse):
            row["val_rmse"] = float(val_rmse[i])
        rows.append(row)
    return rows
