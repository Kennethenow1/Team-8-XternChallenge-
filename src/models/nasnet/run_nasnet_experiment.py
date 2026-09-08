"""Orchestrate NASNetLarge experiment: preprocess → train seeds → eval → report."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# LD_LIBRARY_PATH must be set before TensorFlow is imported
from src.models.nasnet.train_nasnetlarge import configure_nvidia_lib_path

configure_nvidia_lib_path()

from src.models.nasnet import NASNET_ARTIFACTS_DIR, NASNET_REPORTS_DIR, ensure_nasnet_dirs
from src.models.nasnet.evaluate_nasnetlarge import run_evaluation
from src.models.nasnet.preprocess_nasnet import load_config, run_preprocess
from src.models.nasnet.train_nasnetlarge import require_gpu, train_frozen_and_finetune, train_mlp_baseline


def run_experiment(*, skip_train: bool = False, smoke: bool = False) -> dict[str, Any]:
    cfg = load_config()
    ensure_nasnet_dirs()

    print("[nasnet] hardware check ...", flush=True)
    # Eval-only can run on CPU if the GPU is busy with another training job.
    require = bool(cfg.get("training", {}).get("require_gpu", True)) and not skip_train
    hw = require_gpu(require=require)
    print(json.dumps(hw, indent=2), flush=True)

    print("[nasnet] preprocessing (TRAIN-only fit) ...", flush=True)
    prep = run_preprocess(config=cfg, save=True)
    print(
        f"  n_features={prep['n_features']} side={prep['side']} "
        f"train_prev={prep['train_prevalence']:.4f} val_prev={prep['val_prevalence']:.4f}",
        flush=True,
    )
    (NASNET_ARTIFACTS_DIR / "preprocess_summary.json").write_text(
        json.dumps({k: v for k, v in prep.items() if k != "feature_meta"}, indent=2, default=str),
        encoding="utf-8",
    )

    seeds = list(cfg.get("seeds", [42, 123, 2026]))
    if smoke:
        seeds = seeds[:1]
        cfg = json.loads(json.dumps(cfg))  # deep copy
        cfg.setdefault("training", {})
        cfg["training"]["frozen_epochs"] = 2
        cfg["training"]["finetune_epochs"] = 1
        cfg["training"]["do_finetune"] = False
        cfg["training"]["batch_size_candidates"] = [4]
        cfg.setdefault("mlp", {})["epochs"] = 5

    train_summaries: list[dict[str, Any]] = []
    mlp_summaries: list[dict[str, Any]] = []
    shuffle_summary = None

    if not skip_train:
        for seed in seeds:
            print(f"[nasnet] training NASNetLarge seed={seed} ...", flush=True)
            summary = train_frozen_and_finetune(seed=int(seed), config=cfg, label_shuffle=False)
            train_summaries.append(summary)
            (NASNET_ARTIFACTS_DIR / f"train_summary_seed_{seed}.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8"
            )
            print(
                f"  frozen val_pr_auc={summary['frozen']['best_val_pr_auc']} "
                f"time={summary['frozen']['training_time_sec']:.1f}s",
                flush=True,
            )

        print("[nasnet] label-shuffle leakage check ...", flush=True)
        shuffle_summary = train_frozen_and_finetune(
            seed=int(seeds[0]),
            config=cfg,
            label_shuffle=True,
            max_epochs_override=int(cfg.get("training", {}).get("label_shuffle_epochs", 5)),
        )
        (NASNET_ARTIFACTS_DIR / "train_summary_label_shuffle.json").write_text(
            json.dumps(shuffle_summary, indent=2, default=str), encoding="utf-8"
        )
        print(
            f"  shuffle val_pr_auc={shuffle_summary['frozen']['best_val_pr_auc']}",
            flush=True,
        )

        for seed in seeds:
            print(f"[nasnet] training MLP baseline seed={seed} ...", flush=True)
            mlp = train_mlp_baseline(seed=int(seed), config=cfg)
            mlp_summaries.append(mlp)
            print(f"  mlp val_pr_auc={mlp['best_val_pr_auc']}", flush=True)
    else:
        # Reload summaries if present
        for seed in seeds:
            p = NASNET_ARTIFACTS_DIR / f"train_summary_seed_{seed}.json"
            if p.exists():
                train_summaries.append(json.loads(p.read_text(encoding="utf-8")))
        sp = NASNET_ARTIFACTS_DIR / "train_summary_label_shuffle.json"
        if sp.exists():
            shuffle_summary = json.loads(sp.read_text(encoding="utf-8"))
        for seed in seeds:
            mp = NASNET_ARTIFACTS_DIR / f"mlp_baseline_seed_{seed}.keras"
            yp = NASNET_ARTIFACTS_DIR / f"mlp_val_prob_seed_{seed}.npy"
            if yp.exists():
                mlp_summaries.append(
                    {
                        "seed": seed,
                        "y_prob_path": str(yp),
                        "checkpoint": str(mp),
                    }
                )

    print("[nasnet] evaluating on VAL ...", flush=True)
    ev = run_evaluation(
        train_summaries=train_summaries,
        mlp_summaries=mlp_summaries,
        label_shuffle_summary=shuffle_summary,
        config=cfg,
    )
    print(f"[nasnet] report: {ev['report']}", flush=True)
    return {"preprocess": prep, "train": train_summaries, "evaluation": ev}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run NASNetLarge tabular-to-image experiment")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Short epochs / single seed for wiring checks")
    args = parser.parse_args(argv)
    run_experiment(skip_train=args.skip_train, smoke=args.smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
