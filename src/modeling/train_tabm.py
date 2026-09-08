"""TabM trainer on tabm_v1_* (official `tabm` package only; no sklearn fallback)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.model_registry import (
    ARTIFACTS_DIR,
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)


def _load_tabm_column_lists() -> tuple[list[str], list[str]]:
    path = ARTIFACTS_DIR / "feature_columns_tabm_v1.json"
    if path.exists():
        meta = json.loads(path.read_text(encoding="utf-8"))
        cat_cols = list(meta.get("categorical_columns") or [])
        num_cols = list(meta.get("numeric_columns") or [])
        if cat_cols or num_cols:
            return cat_cols, num_cols
    # Fallback: infer from NATIVE_CATEGORICALS
    X_tr, _, _ = load_xy("tabm_v1", "train")
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    num_cols = [c for c in X_tr.columns if c not in cat_cols]
    return cat_cols, num_cols


def _split_xy(
    X: pd.DataFrame, cat_cols: list[str], num_cols: list[str]
) -> tuple[np.ndarray, np.ndarray | None]:
    x_num = X[num_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float32)
    if cat_cols:
        x_cat = X[cat_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.int64).to_numpy()
        return x_num, x_cat
    return x_num, None


def _cat_cardinalities(X_tr: pd.DataFrame, cat_cols: list[str], X_va: pd.DataFrame | None = None) -> list[int]:
    cards: list[int] = []
    for c in cat_cols:
        vals = pd.to_numeric(X_tr[c], errors="coerce").fillna(0).astype(np.int64)
        mx = int(vals.max()) if len(vals) else 0
        if X_va is not None and c in X_va.columns:
            vv = pd.to_numeric(X_va[c], errors="coerce").fillna(0).astype(np.int64)
            if len(vv):
                mx = max(mx, int(vv.max()))
        cards.append(max(mx, 0) + 1)
    return cards


def _predict_proba_tabm(model: Any, x_num: np.ndarray, x_cat: np.ndarray | None, *, device: Any) -> np.ndarray:
    import scipy.special
    import torch

    model.eval()
    batch_size = 4096
    chunks: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, len(x_num), batch_size):
            end = start + batch_size
            xn = torch.as_tensor(x_num[start:end], device=device)
            xc = torch.as_tensor(x_cat[start:end], device=device) if x_cat is not None else None
            logits = model(xn, xc).float()
            if logits.ndim == 3:
                probs = scipy.special.softmax(logits.cpu().numpy(), axis=-1)
                if probs.shape[-1] == 2:
                    p = probs[..., 1].mean(axis=1)
                else:
                    p = probs.mean(axis=1)
            else:
                p = torch.sigmoid(logits.squeeze(-1)).mean(dim=1).cpu().numpy()
            chunks.append(np.asarray(p, dtype=float))
    return np.concatenate(chunks)


def fit_tabm_eval(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    model_name: str = "tabm",
    save: bool = True,
    matrix_prefix: str = "tabm_v1",
) -> dict[str, Any]:
    """Train official TabM on tabm_v1; skip loudly if package/API unavailable."""
    assert_selection_split(SELECTION_SPLIT)
    try:
        import torch
        import torch.nn as nn
        from tabm import TabM
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"tabm/torch not installed: {e}"}

    cfg: dict[str, Any] = {
        "k": 32,
        "n_blocks": 3,
        "d_block": 512,
        "dropout": 0.1,
        "lr": 2e-3,
        "weight_decay": 3e-4,
        "batch_size": 256,
        "patience": 16,
        "max_epochs": 200,
        "gradient_clipping_norm": 1.0,
        "share_training_batches": True,
        "seed": 42,
    }
    if params:
        cfg.update(params)

    try:
        X_tr, y_tr, _ = load_xy(matrix_prefix, "train")
        X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
        y_tr = pd.to_numeric(y_tr, errors="coerce")
        y_va = pd.to_numeric(y_va, errors="coerce")
        mask = y_tr.notna()
        X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
        drop = [c for c in (drop_cols or []) if c in X_tr.columns]
        if drop:
            X_tr = X_tr.drop(columns=drop)
            X_va = X_va.drop(columns=drop)

        cat_cols, num_cols = _load_tabm_column_lists()
        cat_cols = [c for c in cat_cols if c in X_tr.columns]
        num_cols = [c for c in num_cols if c in X_tr.columns]
        cat_cardinalities = _cat_cardinalities(X_tr, cat_cols, X_va)

        x_num_tr, x_cat_tr = _split_xy(X_tr, cat_cols, num_cols)
        x_num_va, x_cat_va = _split_xy(X_va, cat_cols, num_cols)
        # Clip categorical indices into embedding range (unseen val levels)
        if x_cat_tr is not None and x_cat_va is not None:
            for i, card in enumerate(cat_cardinalities):
                hi = max(card - 1, 0)
                x_cat_tr[:, i] = np.clip(x_cat_tr[:, i], 0, hi)
                x_cat_va[:, i] = np.clip(x_cat_va[:, i], 0, hi)
        y_tr_np = y_tr.astype(np.int64).to_numpy()
        y_va_np = y_va.astype(np.int64).to_numpy()
        capacity = load_capacity_mw(meta_va)

        seed = int(cfg["seed"])
        torch.manual_seed(seed)
        np.random.seed(seed)
        # Force CPU: this environment's CUDA driver is unreliable for TabM.
        device = torch.device("cpu")

        make_kwargs: dict[str, Any] = {
            "n_num_features": len(num_cols),
            "cat_cardinalities": cat_cardinalities,
            "d_out": 2,
        }
        for key in ("k", "n_blocks", "d_block", "dropout"):
            if key in cfg:
                make_kwargs[key] = cfg[key]
        model = TabM.make(**make_kwargs).to(device)
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=float(cfg["lr"]),
            weight_decay=float(cfg["weight_decay"]),
        )

        data = {
            "train": {
                "x_num": torch.as_tensor(x_num_tr, device=device),
                "y": torch.as_tensor(y_tr_np, device=device),
            },
            "val": {
                "x_num": torch.as_tensor(x_num_va, device=device),
                "y": torch.as_tensor(y_va_np, device=device),
            },
        }
        if x_cat_tr is not None:
            data["train"]["x_cat"] = torch.as_tensor(x_cat_tr, device=device)
            data["val"]["x_cat"] = torch.as_tensor(x_cat_va, device=device)

        share_batches = bool(cfg["share_training_batches"])
        batch_size = int(cfg["batch_size"])
        train_size = len(y_tr_np)
        k = int(getattr(model, "k", cfg["k"]))

        def apply_model(part: str, idx: torch.Tensor) -> torch.Tensor:
            xn = data[part]["x_num"][idx]
            xc = data[part].get("x_cat")
            xc = xc[idx] if xc is not None else None
            return model(xn, xc).float()

        def loss_fn(y_pred: torch.Tensor, y_true: torch.Tensor) -> torch.Tensor:
            y_pred = y_pred.flatten(0, 1)
            if share_batches:
                y_true = y_true.repeat_interleave(k)
            else:
                y_true = y_true.flatten(0, 1)
            return nn.functional.cross_entropy(y_pred, y_true)

        best_state = deepcopy(model.state_dict())
        best_epoch = -1
        best_val_loss = float("inf")
        remaining_patience = int(cfg["patience"])

        for epoch in range(int(cfg["max_epochs"])):
            batches = (
                torch.randperm(train_size, device=device).split(batch_size)
                if share_batches
                else torch.rand((train_size, k), device=device).argsort(dim=0).split(batch_size, dim=0)
            )
            model.train()
            for batch_idx in batches:
                optimizer.zero_grad()
                loss = loss_fn(apply_model("train", batch_idx), data["train"]["y"][batch_idx])
                loss.backward()
                clip = cfg.get("gradient_clipping_norm")
                if clip is not None:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), float(clip))
                optimizer.step()

            # Early stop on val loss (lower is better)
            model.eval()
            with torch.inference_mode():
                val_losses = []
                for start in range(0, len(y_va_np), batch_size):
                    idx = torch.arange(start, min(start + batch_size, len(y_va_np)), device=device)
                    val_losses.append(float(loss_fn(apply_model("val", idx), data["val"]["y"][idx]).item()))
                val_loss = float(np.mean(val_losses))

            if epoch == 0 or val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = deepcopy(model.state_dict())
                best_epoch = epoch
                remaining_patience = int(cfg["patience"])
            else:
                remaining_patience -= 1
                if remaining_patience < 0:
                    break

        model.load_state_dict(best_state)
        proba = _predict_proba_tabm(model, x_num_va, x_cat_va, device=device)
        metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
        metrics.update(
            {
                "status": "ok",
                "model": model_name,
                "split": SELECTION_SPLIT,
                "best_epoch": int(best_epoch),
                "n_features": int(X_tr.shape[1]),
                "backend": "tabm",
            }
        )
        hyperparams = {
            **cfg,
            "cat_cardinalities": cat_cardinalities,
            "categorical_columns": cat_cols,
            "numeric_columns": num_cols,
            "dropped_features": drop,
            "device": str(device),
        }
        if save:
            preds = meta_va.copy()
            preds["y_true"] = y_va.to_numpy()
            preds["y_prob"] = proba
            preds["capacity_mw"] = capacity.to_numpy()
            save_run_artifacts(
                model_name,
                hyperparams=hyperparams,
                feature_list=feature_list_from_X(X_tr),
                train_metadata={
                    "matrix": matrix_prefix,
                    "n_train": int(len(X_tr)),
                    "n_val": int(len(X_va)),
                    "prevalence_train": float(y_tr.mean()),
                    "prevalence_val": float(y_va.mean()),
                    "categorical_int_cols": cat_cols,
                },
                metrics=metrics,
                val_predictions=preds,
                model_obj={"state_dict": best_state, "hyperparams": hyperparams},
                model_filename="model.tabm.pt.joblib",
            )
        else:
            metrics["_proba"] = proba
            metrics["_model"] = model
            metrics["_params"] = hyperparams
            metrics["_feature_list"] = feature_list_from_X(X_tr)
            metrics["_meta_va"] = meta_va
            metrics["_y_va"] = y_va
            metrics["_capacity"] = capacity
        return metrics
    except Exception as e:
        return {
            "model": model_name,
            "status": "skipped",
            "reason": f"tabm training failed: {type(e).__name__}: {e}",
        }


def train_tabm_default() -> dict[str, Any]:
    return fit_tabm_eval(model_name="tabm", save=True)
