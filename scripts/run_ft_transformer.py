#!/usr/bin/env python3
"""Train FT-Transformer on ftt_v1 (VAL selection only; TEST sealed).

  python scripts/run_ft_transformer.py
  python scripts/run_ft_transformer.py --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.model_registry import ensure_artifact_dirs
from src.modeling.tabm_matrix import run_ftt_matrices
from src.modeling.train_ft_transformer import fit_ft_transformer_eval


def main() -> int:
    parser = argparse.ArgumentParser(description="Train FT-Transformer on ftt_v1 (VAL only)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-epochs", type=int, default=200)
    parser.add_argument("--no-gpu", action="store_true")
    parser.add_argument("--skip-matrix", action="store_true", help="Assume ftt_v1_* already exist")
    args = parser.parse_args()

    ensure_artifact_dirs()
    if not args.skip_matrix:
        print("[ftt] ensuring ftt_v1 matrices (alias of tabm_v1 normalize) ...", flush=True)
        info = run_ftt_matrices()
        print(
            f"  n_features={info['n_features']} paths={list(info['paths'].keys())}",
            flush=True,
        )

    print(f"[ftt] training FT-Transformer seed={args.seed} ...", flush=True)
    metrics = fit_ft_transformer_eval(
        params={
            "seed": int(args.seed),
            "max_epochs": int(args.max_epochs),
            "use_gpu": not args.no_gpu,
        },
        model_name="ft_transformer",
        save=True,
    )
    print(json.dumps({k: v for k, v in metrics.items() if not str(k).startswith("_")}, indent=2, default=str))
    return 0 if metrics.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
