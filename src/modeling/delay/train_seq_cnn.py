"""Temporal 1D CNN on delay_seq_v1. MAX_EPOCHS=100, patience 15, reject <8-epoch smoke unless MAE beats persist."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.modeling.delay.common import pack_metrics
from src.modeling.delay.registry import load_seq, load_xy
from src.modeling.delay_eval_protocol import neural_nets_allowed, persist_baseline, regression_metrics
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split

MIN_EPOCHS_BEFORE_STOP = 8

try:
    import torch
    import torch.nn as nn
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]


if nn is not None:

    class SeqCNNNet(nn.Module):
        """Conv1d → masked GAP → dense delay head (optional GRU)."""

        def __init__(
            self,
            in_ch: int,
            filters1: int,
            filters2: int,
            kernel: int,
            dropout: float,
            use_gru: bool,
        ) -> None:
            super().__init__()
            self.conv1 = nn.Conv1d(in_ch, filters1, kernel, padding=kernel // 2)
            self.conv2 = nn.Conv1d(filters1, filters2, kernel, padding=kernel // 2)
            self.drop = nn.Dropout(dropout)
            self.gru = nn.GRU(filters2, filters2, batch_first=True) if use_gru else None
            self.head = nn.Sequential(nn.Linear(filters2, 64), nn.ReLU(), nn.Dropout(dropout), nn.Linear(64, 1))

        def forward(self, x, mask):
            h = torch.relu(self.conv1(x.transpose(1, 2)))
            h = torch.relu(self.conv2(h))
            h = self.drop(h)
            if self.gru is not None:
                h = h.transpose(1, 2)
                h, _ = self.gru(h)
                mask_e = mask.unsqueeze(-1)
                h = (h * mask_e).sum(1) / mask_e.sum(1).clamp(min=1.0)
            else:
                mask_e = mask.unsqueeze(1)
                denom = mask.sum(dim=1, keepdim=True).clamp(min=1.0)
                h = (h * mask_e).sum(-1) / denom
            return self.head(h).squeeze(-1)


def fit_seq_cnn_delay(
    *,
    seed: int = 42,
    max_epochs: int = 100,
    patience: int = 15,
    lr: float = 1e-3,
    batch_size: int = 64,
    filters1: int = 32,
    filters2: int = 64,
    kernel: int = 3,
    dropout: float = 0.2,
    huber_delta: float = 12.0,
    use_gru: bool = False,
    min_epochs: int = MIN_EPOCHS_BEFORE_STOP,
    model_name: str = "seq_cnn",
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    if not neural_nets_allowed():
        return {"model": model_name, "status": "skipped", "reason": "val labeled < 200; neural nets gated"}
    if torch is None or nn is None:
        return {"model": model_name, "status": "skipped", "reason": "torch unavailable"}

    tr, va = load_seq("train"), load_seq("val")
    X_tr, m_tr, y_tr = tr["X"], tr["mask"], tr["y"]
    X_va, m_va, y_va_np = va["X"], va["mask"], va["y"]
    _, _, meta_va = load_xy("delay_foundation_v1", SELECTION_SPLIT)
    # align length
    n_va = min(len(meta_va), len(y_va_np))
    meta_va = meta_va.iloc[:n_va].reset_index(drop=True)
    y_va_np = y_va_np[:n_va]
    X_va, m_va = X_va[:n_va], m_va[:n_va]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    net = SeqCNNNet(X_tr.shape[-1], filters1, filters2, kernel, dropout, use_gru).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=5, factor=0.5)
    best_mae, best_state, wait = float("inf"), None, 0
    hist: list[dict[str, float]] = []
    n = len(X_tr)
    y_tr_t = torch.as_tensor(y_tr, dtype=torch.float32)
    for epoch in range(int(max_epochs)):
        net.train()
        perm = np.random.default_rng(seed + epoch).permutation(n)
        losses, maes = [], []
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            xb = torch.as_tensor(X_tr[idx], device=device)
            mb = torch.as_tensor(m_tr[idx], device=device)
            yb = torch.as_tensor(y_tr[idx], device=device)
            opt.zero_grad(set_to_none=True)
            pred = net(xb, mb)
            loss = torch.nn.functional.huber_loss(pred, yb, delta=huber_delta)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
            maes.append(float((pred.detach() - yb).abs().mean().cpu()))
        net.eval()
        with torch.inference_mode():
            pred_va = net(torch.as_tensor(X_va, device=device), torch.as_tensor(m_va, device=device)).cpu().numpy()
        mae = float(np.mean(np.abs(pred_va - y_va_np)))
        hist.append({"step": float(epoch), "train_loss": float(np.mean(losses)), "train_mae": float(np.mean(maes)), "val_loss": mae, "val_mae": mae})
        sched.step(mae)
        if mae + 1e-6 < best_mae:
            best_mae, wait = mae, 0
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
        else:
            wait += 1
            if wait >= patience and epoch + 1 >= min_epochs:
                break
    if best_state:
        net.load_state_dict(best_state)
    net.eval()
    with torch.inference_mode():
        pred_va = net(torch.as_tensor(X_va, device=device), torch.as_tensor(m_va, device=device)).cpu().numpy()
    persist_mae = regression_metrics(y_va_np, persist_baseline(meta_va))["mae"]
    extra = {
        "n_features": int(X_tr.shape[-1]),
        "n_epochs": len(hist),
        "device": str(device),
        "use_gru": use_gru,
        "_model": net,
    }
    m = pack_metrics(
        model=model_name,
        y_va=pd.Series(y_va_np),
        pred=pred_va,
        meta_va=meta_va,
        history=hist,
        extra=extra,
    )
    if len(hist) < min_epochs and not (np.isfinite(m.get("mae")) and np.isfinite(persist_mae) and m["mae"] < persist_mae):
        m["status"] = "skipped"
        m["reason"] = f"rejected smoke run: {len(hist)} epochs < {min_epochs} and MAE did not beat persist"
    return m
