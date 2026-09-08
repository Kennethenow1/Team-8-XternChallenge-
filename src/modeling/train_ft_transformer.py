"""FT-Transformer trainer on ftt_v1_* (alias of tabm_v1 normalize)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Sequence

import numpy as np
import pandas as pd

from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split, full_eval_metrics
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.ft_transformer_model import FTTransformer
from src.modeling.model_registry import (
    ARTIFACTS_DIR,
    feature_list_from_X,
    load_capacity_mw,
    load_xy,
    save_run_artifacts,
)


def _load_ftt_column_lists() -> tuple[list[str], list[str]]:
    for name in ("feature_columns_ftt_v1.json", "feature_columns_tabm_v1.json"):
        path = ARTIFACTS_DIR / name
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            cat_cols = list(meta.get("categorical_columns") or [])
            num_cols = list(meta.get("numeric_columns") or [])
            if cat_cols or num_cols:
                return cat_cols, num_cols
    X_tr, _, _ = load_xy("ftt_v1", "train")
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    num_cols = [c for c in X_tr.columns if c not in cat_cols]
    return cat_cols, num_cols


def _split_xy(
    X: pd.DataFrame, cat_cols: list[str], num_cols: list[str]
) -> tuple[np.ndarray | None, np.ndarray | None]:
    x_num = None
    x_cat = None
    if num_cols:
        x_num = X[num_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float32)
        x_num = np.nan_to_num(x_num, nan=0.0)
    if cat_cols:
        x_cat = X[cat_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.int64).to_numpy()
    return x_num, x_cat


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


def _average_precision_np(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score

    if y_true.sum() == 0 or y_true.sum() == len(y_true):
        return float("nan")
    return float(average_precision_score(y_true, y_prob))


def fit_ft_transformer_eval(
    *,
    params: dict[str, Any] | None = None,
    drop_cols: Sequence[str] | None = None,
    model_name: str = "ft_transformer",
    save: bool = True,
    matrix_prefix: str = "ftt_v1",
) -> dict[str, Any]:
    """Train compact FT-Transformer on ftt_v1; evaluate on VAL only."""
    assert_selection_split(SELECTION_SPLIT)
    try:
        import torch
        import torch.nn as nn
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"torch not installed: {e}"}

    cfg: dict[str, Any] = {
        "d_token": 64,
        "n_blocks": 2,
        "n_heads": 4,
        "d_ffn_factor": 2.0,
        "dropout": 0.15,
        "lr": 1e-3,
        "weight_decay": 1e-4,
        "batch_size": 256,
        "patience": 20,
        "max_epochs": 200,
        "gradient_clipping_norm": 1.0,
        "seed": 42,
        "use_gpu": True,
    }
    if params:
        cfg.update(params)

    try:
        X_tr, y_tr, _ = load_xy(matrix_prefix, "train")
        X_va, y_va, meta_va = load_xy(matrix_prefix, SELECTION_SPLIT)
    except FileNotFoundError as e:
        return {"model": model_name, "status": "skipped", "reason": f"missing matrix: {e}"}

    y_tr = pd.to_numeric(y_tr, errors="coerce")
    y_va = pd.to_numeric(y_va, errors="coerce")
    mask = y_tr.notna()
    X_tr, y_tr = X_tr.loc[mask].copy(), y_tr.loc[mask]
    drop = [c for c in (drop_cols or []) if c in X_tr.columns]
    if drop:
        X_tr = X_tr.drop(columns=drop)
        X_va = X_va.drop(columns=drop)

    cat_cols, num_cols = _load_ftt_column_lists()
    cat_cols = [c for c in cat_cols if c in X_tr.columns]
    num_cols = [c for c in num_cols if c in X_tr.columns]
    cat_cardinalities = _cat_cardinalities(X_tr, cat_cols, X_va)

    x_num_tr, x_cat_tr = _split_xy(X_tr, cat_cols, num_cols)
    x_num_va, x_cat_va = _split_xy(X_va, cat_cols, num_cols)
    if x_cat_tr is not None and x_cat_va is not None:
        for i, card in enumerate(cat_cardinalities):
            hi = max(card - 1, 0)
            x_cat_tr[:, i] = np.clip(x_cat_tr[:, i], 0, hi)
            x_cat_va[:, i] = np.clip(x_cat_va[:, i], 0, hi)

    y_tr_np = y_tr.astype(np.float32).to_numpy()
    y_va_np = y_va.astype(np.float32).to_numpy()
    capacity = load_capacity_mw(meta_va)

    seed = int(cfg["seed"])
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = torch.device("cpu")
    if bool(cfg.get("use_gpu", True)) and torch.cuda.is_available():
        try:
            device = torch.device("cuda")
            torch.cuda.manual_seed_all(seed)
        except Exception:
            device = torch.device("cpu")

    model = FTTransformer(
        n_num_features=len(num_cols),
        cat_cardinalities=cat_cardinalities,
        d_token=int(cfg["d_token"]),
        n_blocks=int(cfg["n_blocks"]),
        n_heads=int(cfg["n_heads"]),
        d_ffn_factor=float(cfg["d_ffn_factor"]),
        dropout=float(cfg["dropout"]),
        d_out=1,
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["lr"]),
        weight_decay=float(cfg["weight_decay"]),
    )

    # pos_weight for class imbalance
    n_pos = float(max(y_tr_np.sum(), 1.0))
    n_neg = float(max(len(y_tr_np) - y_tr_np.sum(), 1.0))
    pos_weight = torch.tensor([n_neg / n_pos], device=device, dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    def _batch_tensors(idx: np.ndarray) -> tuple[torch.Tensor | None, torch.Tensor | None, torch.Tensor]:
        xn = (
            torch.as_tensor(x_num_tr[idx], device=device, dtype=torch.float32)
            if x_num_tr is not None
            else None
        )
        xc = (
            torch.as_tensor(x_cat_tr[idx], device=device, dtype=torch.long)
            if x_cat_tr is not None
            else None
        )
        yt = torch.as_tensor(y_tr_np[idx], device=device, dtype=torch.float32)
        return xn, xc, yt

    @torch.inference_mode()
    def _predict(x_num: np.ndarray | None, x_cat: np.ndarray | None) -> np.ndarray:
        model.eval()
        n = len(x_num) if x_num is not None else len(x_cat)  # type: ignore[arg-type]
        out: list[np.ndarray] = []
        bs = int(cfg["batch_size"])
        for start in range(0, n, bs):
            end = start + bs
            xn = (
                torch.as_tensor(x_num[start:end], device=device, dtype=torch.float32)
                if x_num is not None
                else None
            )
            xc = (
                torch.as_tensor(x_cat[start:end], device=device, dtype=torch.long)
                if x_cat is not None
                else None
            )
            logits = model(xn, xc)
            out.append(torch.sigmoid(logits).detach().cpu().numpy())
        return np.concatenate(out).astype(float)

    best_state = deepcopy(model.state_dict())
    best_epoch = -1
    best_val_pr = -1.0
    remaining = int(cfg["patience"])
    history: list[dict[str, float]] = []

    train_size = len(y_tr_np)
    batch_size = int(cfg["batch_size"])

    for epoch in range(int(cfg["max_epochs"])):
        model.train()
        order = np.random.permutation(train_size)
        for start in range(0, train_size, batch_size):
            idx = order[start : start + batch_size]
            xn, xc, yt = _batch_tensors(idx)
            optimizer.zero_grad(set_to_none=True)
            logits = model(xn, xc)
            loss = loss_fn(logits, yt)
            loss.backward()
            clip = cfg.get("gradient_clipping_norm")
            if clip is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(clip))
            optimizer.step()

        val_prob = _predict(x_num_va, x_cat_va)
        val_pr = _average_precision_np(y_va_np.astype(int), val_prob)
        # also track val BCE for logging
        with torch.inference_mode():
            vn = (
                torch.as_tensor(x_num_va, device=device, dtype=torch.float32)
                if x_num_va is not None
                else None
            )
            vc = (
                torch.as_tensor(x_cat_va, device=device, dtype=torch.long)
                if x_cat_va is not None
                else None
            )
            vt = torch.as_tensor(y_va_np, device=device, dtype=torch.float32)
            vloss = float(loss_fn(model(vn, vc), vt).item())
        history.append({"epoch": float(epoch), "val_pr_auc": float(val_pr), "val_loss": vloss})

        improved = np.isfinite(val_pr) and val_pr > best_val_pr + 1e-6
        if improved or best_epoch < 0:
            best_val_pr = float(val_pr) if np.isfinite(val_pr) else best_val_pr
            best_state = deepcopy(model.state_dict())
            best_epoch = epoch
            remaining = int(cfg["patience"])
        else:
            remaining -= 1
            if remaining < 0:
                break

        if epoch % 10 == 0 or improved:
            print(
                f"[ftt] epoch={epoch} val_pr_auc={val_pr:.4f} val_loss={vloss:.4f} "
                f"best={best_val_pr:.4f}@{best_epoch}",
                flush=True,
            )

    model.load_state_dict(best_state)
    proba = _predict(x_num_va, x_cat_va)
    metrics = full_eval_metrics(y_va.astype(float), proba, capacity)
    metrics.update(
        {
            "status": "ok",
            "model": model_name,
            "split": SELECTION_SPLIT,
            "best_epoch": int(best_epoch),
            "best_val_pr_auc_train_monitor": float(best_val_pr),
            "n_features": int(X_tr.shape[1]),
            "backend": "ft_transformer",
            "device": str(device),
        }
    )
    hyperparams = {
        **cfg,
        "cat_cardinalities": cat_cardinalities,
        "categorical_columns": cat_cols,
        "numeric_columns": num_cols,
        "dropped_features": drop,
        "pos_weight": float(n_neg / n_pos),
        "device": str(device),
        "history_tail": history[-5:],
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
            model_obj={"state_dict": {k: v.cpu() for k, v in best_state.items()}, "hyperparams": hyperparams},
            model_filename="model.ftt.pt.joblib",
        )
        hist_path = ARTIFACTS_DIR / "models" / model_name / "train_history.json"
        hist_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    else:
        metrics["_proba"] = proba
        metrics["_params"] = hyperparams
    return metrics


def train_ft_transformer_default() -> dict[str, Any]:
    return fit_ft_transformer_eval(model_name="ft_transformer", save=True)
