"""Compact FT-Transformer (Gorishniy et al.) for tabular binary classification."""

from __future__ import annotations

from typing import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F


class _Tokenizer(nn.Module):
    """One token per numeric feature + one embedding per categorical feature + CLS."""

    def __init__(
        self,
        *,
        n_num: int,
        cat_cardinalities: Sequence[int],
        d_token: int,
    ) -> None:
        super().__init__()
        self.n_num = int(n_num)
        self.n_cat = len(cat_cardinalities)
        self.d_token = int(d_token)
        self.cls = nn.Parameter(torch.zeros(1, 1, d_token))
        nn.init.normal_(self.cls, std=0.02)
        self.num_weight = nn.Parameter(torch.empty(n_num, d_token)) if n_num else None
        self.num_bias = nn.Parameter(torch.empty(n_num, d_token)) if n_num else None
        if self.num_weight is not None:
            nn.init.kaiming_uniform_(self.num_weight, a=5**0.5)
            nn.init.zeros_(self.num_bias)
        self.cat_embeddings = nn.ModuleList(
            [nn.Embedding(int(card), d_token) for card in cat_cardinalities]
        )
        for emb in self.cat_embeddings:
            nn.init.normal_(emb.weight, std=0.02)

    def forward(self, x_num: torch.Tensor | None, x_cat: torch.Tensor | None) -> torch.Tensor:
        tokens: list[torch.Tensor] = []
        batch = (x_num if x_num is not None else x_cat).shape[0]
        tokens.append(self.cls.expand(batch, -1, -1))
        if self.n_num and x_num is not None and self.num_weight is not None:
            # (B, n_num, d) = x[..., None] * W + b
            tokens.append(x_num.unsqueeze(-1) * self.num_weight + self.num_bias)
        if self.n_cat and x_cat is not None:
            cat_toks = [emb(x_cat[:, i]) for i, emb in enumerate(self.cat_embeddings)]
            tokens.append(torch.stack(cat_toks, dim=1))
        return torch.cat(tokens, dim=1)


class _TransformerBlock(nn.Module):
    def __init__(self, d_token: int, n_heads: int, d_ffn: int, dropout: float) -> None:
        super().__init__()
        self.attn = nn.MultiheadAttention(d_token, n_heads, dropout=dropout, batch_first=True)
        self.lin1 = nn.Linear(d_token, d_ffn)
        self.lin2 = nn.Linear(d_ffn, d_token)
        self.norm1 = nn.LayerNorm(d_token)
        self.norm2 = nn.LayerNorm(d_token)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        a, _ = self.attn(h, h, h, need_weights=False)
        x = x + self.drop(a)
        h = self.norm2(x)
        h = self.lin2(self.drop(F.gelu(self.lin1(h))))
        return x + self.drop(h)


class FTTransformer(nn.Module):
    """Feature Tokenizer + Transformer + CLS head for binary logits."""

    def __init__(
        self,
        *,
        n_num_features: int,
        cat_cardinalities: Sequence[int],
        d_token: int = 64,
        n_blocks: int = 2,
        n_heads: int = 4,
        d_ffn_factor: float = 2.0,
        dropout: float = 0.15,
        d_out: int = 1,
    ) -> None:
        super().__init__()
        if d_token % n_heads != 0:
            raise ValueError(f"d_token={d_token} must be divisible by n_heads={n_heads}")
        d_ffn = max(int(d_token * d_ffn_factor), d_token)
        self.tokenizer = _Tokenizer(
            n_num=n_num_features,
            cat_cardinalities=cat_cardinalities,
            d_token=d_token,
        )
        self.blocks = nn.ModuleList(
            [_TransformerBlock(d_token, n_heads, d_ffn, dropout) for _ in range(n_blocks)]
        )
        self.head_norm = nn.LayerNorm(d_token)
        self.head = nn.Sequential(
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_token, d_out),
        )

    def forward(self, x_num: torch.Tensor | None, x_cat: torch.Tensor | None) -> torch.Tensor:
        x = self.tokenizer(x_num, x_cat)
        for block in self.blocks:
            x = block(x)
        cls = self.head_norm(x[:, 0])
        return self.head(cls).squeeze(-1)
