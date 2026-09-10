"""FT-Transformer Huber regression on delay_ftt_v1. Log device. Max 200, patience 20 on val MAE."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.delay_eval_protocol import neural_nets_allowed
from src.modeling.delay_feature_policy import NATIVE_CATEGORICALS
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split
from src.modeling.ft_transformer_model import FTTransformer


def fit_ft_transformer_delay(
    *,
    seed: int = 42,
    use_gpu: bool = True,
    max_epochs: int = 200,
    patience: int = 20,
    lr: float = 1e-3,
    d_token: int = 64,
    n_blocks: int = 2,
    n_heads: int = 4,
    dropout: float = 0.15,
    batch_size: int = 256,
    model_name: str = "ft_transformer",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    if not neural_nets_allowed():
        return {"model": model_name, "status": "skipped", "reason": "val labeled < 200; neural nets gated"}
    try:
        import torch
    except ImportError as e:
        return {"model": model_name, "status": "skipped", "reason": f"torch unavailable: {e}"}

    device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
    X_tr, y_tr, _ = load_xy("delay_ftt_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_ftt_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr = X_tr.loc[mtr], y_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva], y_va.loc[mva], meta_va.loc[mva]
    cat_cols = [c for c in NATIVE_CATEGORICALS if c in X_tr.columns]
    num_cols = [c for c in X_tr.columns if c not in cat_cols]
    x_num = X_tr[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(np.float32)
    x_num_va = X_va[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(np.float32)
    x_cat = X_tr[cat_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.int64).to_numpy() if cat_cols else None
    x_cat_va = X_va[cat_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(np.int64).to_numpy() if cat_cols else None
    cards = [int(max(X_tr[c].max(), X_va[c].max()) + 1) for c in cat_cols] if cat_cols else []
    y = y_tr.astype(np.float32).to_numpy()
    yv = y_va.astype(np.float32).to_numpy()
    torch.manual_seed(seed)
    model = FTTransformer(
        n_num_features=x_num.shape[1],
        cat_cardinalities=cards,
        d_token=d_token,
        n_blocks=n_blocks,
        n_heads=n_heads,
        dropout=dropout,
        d_out=1,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    best_mae, best_state, wait = float("inf"), None, 0
    hist: list[dict[str, float]] = []
    n = len(x_num)
    for epoch in range(int(max_epochs)):
        model.train()
        perm = np.random.default_rng(seed + epoch).permutation(n)
        losses = []
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            xn = torch.as_tensor(x_num[idx], device=device)
            yc = torch.as_tensor(y[idx], device=device)
            xc = torch.as_tensor(x_cat[idx], device=device) if x_cat is not None else None
            opt.zero_grad(set_to_none=True)
            pred = model(xn, xc)
            loss = torch.nn.functional.huber_loss(pred, yc, delta=12.0)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
        model.eval()
        with torch.inference_mode():
            pred_np = model(
                torch.as_tensor(x_num_va, device=device),
                torch.as_tensor(x_cat_va, device=device) if x_cat_va is not None else None,
            ).cpu().numpy()
        mae = float(np.mean(np.abs(pred_np - yv)))
        hist.append({"step": float(epoch), "train_loss": float(np.mean(losses)), "val_loss": mae, "val_mae": mae})
        if mae + 1e-6 < best_mae:
            best_mae, wait, best_state = mae, 0, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience:
                break
    if best_state:
        model.load_state_dict(best_state)
    model.eval()
    with torch.inference_mode():
        pred_np = model(
            torch.as_tensor(x_num_va, device=device),
            torch.as_tensor(x_cat_va, device=device) if x_cat_va is not None else None,
        ).cpu().numpy()
    extra = {
        "n_features": int(X_tr.shape[1]),
        "device": str(device),
        "best_epoch": int(np.argmin([h["val_mae"] for h in hist])) if hist else 0,
        "_model": model,
    }
    return pack_metrics(model=model_name, y_va=y_va, pred=np.asarray(pred_np, dtype=float), meta_va=meta_va, history=hist, extra=extra)
