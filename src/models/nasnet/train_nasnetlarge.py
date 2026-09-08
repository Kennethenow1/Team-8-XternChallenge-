"""Train NASNetLarge (frozen head + optional last-cell fine-tune) and tabular MLP baseline."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.common.paths import REPO_ROOT
from src.models.nasnet import NASNET_ARTIFACTS_DIR, NASNET_REPORTS_DIR, ensure_nasnet_dirs
from src.models.nasnet.build_nasnet_dataset import make_tf_dataset, matrices_to_xy
from src.models.nasnet.preprocess_nasnet import load_config, load_ready_matrices


def configure_nvidia_lib_path() -> None:
    """Ensure pip-installed NVIDIA libs are on LD_LIBRARY_PATH for TF GPU."""
    try:
        import nvidia  # type: ignore
        from pathlib import Path as P

        roots = []
        base = P(nvidia.__file__).resolve().parent
        # Include both package lib dirs (nvidia/cudnn/lib) and umbrella trees (nvidia/cu13/lib)
        for lib in sorted({p for p in base.glob("*/lib") if p.is_dir()} | {p for p in base.glob("*/*/lib") if p.is_dir()}):
            roots.append(str(lib))
        if roots:
            cur = os.environ.get("LD_LIBRARY_PATH", "")
            merged = ":".join(roots + ([cur] if cur else []))
            os.environ["LD_LIBRARY_PATH"] = merged
    except Exception:
        pass


def require_gpu(*, require: bool = True) -> dict[str, Any]:
    configure_nvidia_lib_path()
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    report = {
        "tensorflow_version": tf.__version__,
        "gpus": [g.name for g in gpus],
        "n_gpus": len(gpus),
    }
    if require and not gpus:
        raise RuntimeError(
            "NASNetLarge experiment requires a CUDA GPU visible to TensorFlow. "
            f"Hardware report: {json.dumps(report)}. "
            "Refusing an impractically long CPU run. "
            "Tip: ensure nvidia pip libs are installed and LD_LIBRARY_PATH includes "
            "site-packages/nvidia/*/lib."
        )
    for g in gpus:
        try:
            tf.config.experimental.set_memory_growth(g, True)
        except Exception:
            pass
    return report


def set_global_seed(seed: int) -> None:
    import random

    import tensorflow as tf

    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:
        pass


def enable_mixed_precision() -> bool:
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    if not gpus:
        return False
    tf.keras.mixed_precision.set_global_policy("mixed_float16")
    return True


def class_weights_from_labels(y: np.ndarray) -> dict[int, float]:
    y = np.asarray(y).astype(int)
    n = len(y)
    n0 = int((y == 0).sum())
    n1 = int((y == 1).sum())
    if n0 == 0 or n1 == 0:
        return {0: 1.0, 1: 1.0}
    return {0: n / (2.0 * n0), 1: n / (2.0 * n1)}


def build_nasnet_model(*, l2: float = 1e-4, dense_256: int = 256, dense_64: int = 64,
                       dropout_1: float = 0.5, dropout_2: float = 0.3) -> Any:
    import tensorflow as tf

    base = tf.keras.applications.NASNetLarge(
        include_top=False,
        weights="imagenet",
        input_shape=(331, 331, 3),
        pooling="avg",
    )
    base.trainable = False
    reg = tf.keras.regularizers.l2(l2)
    inputs = tf.keras.Input(shape=(331, 331, 3), name="image")
    x = base(inputs, training=False)
    x = tf.keras.layers.BatchNormalization(name="head_bn")(x)
    x = tf.keras.layers.Dense(dense_256, activation="relu", kernel_regularizer=reg, name="head_dense256")(x)
    x = tf.keras.layers.Dropout(dropout_1, name="head_drop1")(x)
    x = tf.keras.layers.Dense(dense_64, activation="relu", kernel_regularizer=reg, name="head_dense64")(x)
    x = tf.keras.layers.Dropout(dropout_2, name="head_drop2")(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid", dtype="float32", name="withdraw_prob")(x)
    model = tf.keras.Model(inputs, outputs, name="nasnetlarge_withdraw")
    model.base_model = base  # type: ignore[attr-defined]
    return model


def compile_model(model: Any, *, learning_rate: float) -> None:
    import tensorflow as tf

    metrics = [
        tf.keras.metrics.AUC(curve="PR", name="pr_auc", num_thresholds=1000),
        tf.keras.metrics.AUC(curve="ROC", name="roc_auc", num_thresholds=1000),
        tf.keras.metrics.BinaryCrossentropy(name="log_loss"),
    ]
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=metrics,
    )


def _callbacks(ckpt_path: Path, cfg_train: dict[str, Any]) -> list[Any]:
    import tensorflow as tf

    return [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pr_auc",
            patience=int(cfg_train.get("early_stopping_patience", 8)),
            mode="max",
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_pr_auc",
            patience=int(cfg_train.get("reduce_lr_patience", 3)),
            factor=float(cfg_train.get("reduce_lr_factor", 0.5)),
            min_lr=float(cfg_train.get("min_lr", 1e-7)),
            mode="max",
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(ckpt_path),
            monitor="val_pr_auc",
            save_best_only=True,
            mode="max",
        ),
    ]


def unfreeze_last_nasnet_cell(base_model: Any) -> int:
    """Unfreeze trailing NASNet layers (last cell/block); keep BN frozen."""
    layers = list(base_model.layers)
    # Heuristic: unfreeze last ~15% of layers (covers final cell)
    n_unfreeze = max(20, len(layers) // 8)
    start = len(layers) - n_unfreeze
    n = 0
    for i, layer in enumerate(layers):
        if i < start:
            layer.trainable = False
        else:
            if isinstance(layer, type(base_model.layers[0])) and "batch" in layer.name.lower():
                layer.trainable = False
            elif "batch_normalization" in layer.name.lower() or layer.__class__.__name__ == "BatchNormalization":
                layer.trainable = False
            else:
                layer.trainable = True
                n += 1
    return n


def probe_batch_size(
    model_builder,
    x_sample: np.ndarray,
    y_sample: np.ndarray,
    *,
    side: int,
    candidates: list[int],
) -> int:
    import tensorflow as tf

    best = candidates[0]
    for bs in candidates:
        try:
            tf.keras.backend.clear_session()
            model = model_builder()
            compile_model(model, learning_rate=1e-4)
            ds = make_tf_dataset(
                x_sample[: max(bs * 2, bs)],
                y_sample[: max(bs * 2, bs)],
                side=side,
                batch_size=bs,
                shuffle=False,
            )
            model.fit(ds, epochs=1, verbose=0)
            best = bs
            del model
            tf.keras.backend.clear_session()
        except Exception as e:  # noqa: BLE001
            print(f"[nasnet] batch_size={bs} failed: {e}", flush=True)
            tf.keras.backend.clear_session()
            break
    return best


def peak_gpu_memory_mb() -> float | None:
    try:
        import tensorflow as tf

        infos = tf.config.experimental.get_memory_info("GPU:0")
        return float(infos.get("peak", infos.get("current", 0.0)) / (1024**2))
    except Exception:
        return None


def _reload_checkpoint_weights(model: Any, ckpt_path: Path) -> None:
    """Copy weights from a full .keras ModelCheckpoint into the live model."""
    import tensorflow as tf

    if not ckpt_path.exists():
        return
    best = tf.keras.models.load_model(str(ckpt_path))
    model.set_weights(best.get_weights())
    del best


def train_frozen_and_finetune(
    *,
    seed: int,
    config: dict[str, Any] | None = None,
    label_shuffle: bool = False,
    max_epochs_override: int | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    ensure_nasnet_dirs()
    hw = require_gpu(require=bool(cfg.get("training", {}).get("require_gpu", True)))
    set_global_seed(seed)
    mixed = enable_mixed_precision()

    train_df, val_df, cols, target = load_ready_matrices()
    roles = json.loads((NASNET_ARTIFACTS_DIR / "nasnet_feature_roles.json").read_text(encoding="utf-8"))
    side = int(roles["side"])
    x_tr, y_tr = matrices_to_xy(train_df, cols, target)
    x_va, y_va = matrices_to_xy(val_df, cols, target)
    if label_shuffle:
        rng = np.random.default_rng(seed)
        y_tr = rng.permutation(y_tr)

    tcfg = cfg.get("training", {})
    cw = class_weights_from_labels(y_tr)
    batch_size = int(tcfg.get("batch_size", 4))

    def _builder():
        return build_nasnet_model(
            l2=float(tcfg.get("l2", 1e-4)),
            dense_256=int(tcfg.get("dense_256", 256)),
            dense_64=int(tcfg.get("dense_64", 64)),
            dropout_1=float(tcfg.get("dropout_1", 0.5)),
            dropout_2=float(tcfg.get("dropout_2", 0.3)),
        )

    # Probe batch size once for primary runs
    if not label_shuffle and seed == int(cfg.get("seeds", [42])[0]):
        candidates = [int(x) for x in tcfg.get("batch_size_candidates", [4, 8])]
        batch_size = probe_batch_size(_builder, x_tr, y_tr, side=side, candidates=candidates)
        (NASNET_ARTIFACTS_DIR / "chosen_batch_size.json").write_text(
            json.dumps({"batch_size": batch_size}, indent=2), encoding="utf-8"
        )
    elif (NASNET_ARTIFACTS_DIR / "chosen_batch_size.json").exists():
        batch_size = int(json.loads((NASNET_ARTIFACTS_DIR / "chosen_batch_size.json").read_text())["batch_size"])

    import tensorflow as tf

    tf.keras.backend.clear_session()
    set_global_seed(seed)
    model = _builder()
    compile_model(model, learning_rate=float(tcfg.get("learning_rate", 1e-4)))

    tag = f"shuffle_{seed}" if label_shuffle else f"seed_{seed}"
    ckpt_frozen = NASNET_ARTIFACTS_DIR / f"nasnetlarge_frozen_best_{tag}.keras"
    if not label_shuffle and seed == int(cfg.get("seeds", [42])[0]):
        # Canonical path required by plan for primary seed artifact
        ckpt_frozen_canon = NASNET_ARTIFACTS_DIR / "nasnetlarge_frozen_best.keras"
    else:
        ckpt_frozen_canon = ckpt_frozen

    ds_tr = make_tf_dataset(
        x_tr,
        y_tr,
        side=side,
        batch_size=batch_size,
        shuffle=True,
        shuffle_buffer=int(tcfg.get("shuffle_buffer", 1024)),
        seed=seed,
    )
    ds_va = make_tf_dataset(x_va, y_va, side=side, batch_size=batch_size, shuffle=False)

    epochs = int(max_epochs_override or tcfg.get("frozen_epochs", 50))
    if label_shuffle:
        epochs = int(tcfg.get("label_shuffle_epochs", 5))

    t0 = time.perf_counter()
    hist = model.fit(
        ds_tr,
        validation_data=ds_va,
        epochs=epochs,
        class_weight=cw,
        callbacks=_callbacks(ckpt_frozen_canon, tcfg) if not label_shuffle else [],
        verbose=1,
    )
    frozen_time = time.perf_counter() - t0
    best_epoch = int(np.argmax(hist.history.get("val_pr_auc", [0])) + 1) if hist.history.get("val_pr_auc") else None

    # Save history
    hist_path = NASNET_ARTIFACTS_DIR / f"history_frozen_{tag}.json"
    hist_path.write_text(json.dumps({k: [float(x) for x in v] for k, v in hist.history.items()}, indent=2), encoding="utf-8")

    if not label_shuffle:
        model.save(ckpt_frozen_canon)

    finetune_result = None
    if (not label_shuffle) and bool(tcfg.get("do_finetune", True)):
        # Fine-tune last cell
        n_unfrozen = unfreeze_last_nasnet_cell(model.base_model)
        # Keep head BN trainable? Spec: Keep BatchNormalization layers frozen
        for layer in model.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        compile_model(model, learning_rate=float(tcfg.get("finetune_learning_rate", 1e-6)))
        ckpt_ft = NASNET_ARTIFACTS_DIR / f"nasnetlarge_finetuned_best_{tag}.keras"
        ckpt_ft_canon = (
            NASNET_ARTIFACTS_DIR / "nasnetlarge_finetuned_best.keras"
            if seed == int(cfg.get("seeds", [42])[0])
            else ckpt_ft
        )
        t1 = time.perf_counter()
        hist_ft = model.fit(
            ds_tr,
            validation_data=ds_va,
            epochs=int(tcfg.get("finetune_epochs", 20)),
            class_weight=cw,
            callbacks=_callbacks(ckpt_ft_canon, tcfg),
            verbose=1,
        )
        ft_time = time.perf_counter() - t1
        model.save(ckpt_ft_canon)
        (NASNET_ARTIFACTS_DIR / f"history_finetune_{tag}.json").write_text(
            json.dumps({k: [float(x) for x in v] for k, v in hist_ft.history.items()}, indent=2),
            encoding="utf-8",
        )
        finetune_result = {
            "n_unfrozen_layers": n_unfrozen,
            "best_val_pr_auc": float(max(hist_ft.history.get("val_pr_auc", [float("nan")]))),
            "training_time_sec": ft_time,
            "checkpoint": str(ckpt_ft_canon),
            "improved": float(max(hist_ft.history.get("val_pr_auc", [0])))
            > float(max(hist.history.get("val_pr_auc", [0]))),
        }

    trainable = int(np.sum([np.prod(v.shape) for v in model.trainable_weights]))
    nontrain = int(np.sum([np.prod(v.shape) for v in model.non_trainable_weights]))

    return {
        "seed": seed,
        "label_shuffle": label_shuffle,
        "hardware": hw,
        "mixed_precision": mixed,
        "batch_size": batch_size,
        "class_weights": {str(k): float(v) for k, v in cw.items()},
        "train_prevalence": float(y_tr.mean()),
        "val_prevalence": float(y_va.mean()),
        "n_train": int(len(y_tr)),
        "n_val": int(len(y_va)),
        "n_class_0": int((y_tr == 0).sum()),
        "n_class_1": int((y_tr == 1).sum()),
        "frozen": {
            "best_val_pr_auc": float(max(hist.history.get("val_pr_auc", [float("nan")]))),
            "best_epoch": best_epoch,
            "training_time_sec": frozen_time,
            "checkpoint": str(ckpt_frozen_canon),
            "history_path": str(hist_path),
        },
        "finetune": finetune_result,
        "parameter_count": {"trainable": trainable, "non_trainable": nontrain, "total": trainable + nontrain},
        "peak_gpu_memory_mb": peak_gpu_memory_mb(),
    }


def build_mlp(n_features: int, *, cfg: dict[str, Any]) -> Any:
    import tensorflow as tf

    reg = tf.keras.regularizers.l2(1e-4)
    inputs = tf.keras.Input(shape=(n_features,), name="features")
    x = tf.keras.layers.Dense(int(cfg.get("dense_256", 256)), activation="relu", kernel_regularizer=reg)(inputs)
    x = tf.keras.layers.Dropout(float(cfg.get("dropout", 0.3)))(x)
    x = tf.keras.layers.Dense(int(cfg.get("dense_64", 64)), activation="relu", kernel_regularizer=reg)(x)
    x = tf.keras.layers.Dropout(float(cfg.get("dropout", 0.3)))(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid", dtype="float32")(x)
    return tf.keras.Model(inputs, outputs, name="tabular_mlp_baseline")


def train_mlp_baseline(*, seed: int, config: dict[str, Any] | None = None) -> dict[str, Any]:
    import tensorflow as tf

    cfg = config or load_config()
    set_global_seed(seed)
    train_df, val_df, cols, target = load_ready_matrices()
    x_tr, y_tr = matrices_to_xy(train_df, cols, target)
    x_va, y_va = matrices_to_xy(val_df, cols, target)
    mcfg = cfg.get("mlp", {})
    cw = class_weights_from_labels(y_tr)
    model = build_mlp(len(cols), cfg=mcfg)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=float(mcfg.get("learning_rate", 1e-3))),
        loss=tf.keras.losses.BinaryCrossentropy(),
        metrics=[
            tf.keras.metrics.AUC(curve="PR", name="pr_auc", num_thresholds=1000),
            tf.keras.metrics.AUC(curve="ROC", name="roc_auc", num_thresholds=1000),
        ],
    )
    cb = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pr_auc", patience=8, mode="max", restore_best_weights=True
        )
    ]
    t0 = time.perf_counter()
    hist = model.fit(
        x_tr,
        y_tr,
        validation_data=(x_va, y_va),
        epochs=int(mcfg.get("epochs", 50)),
        batch_size=64,
        class_weight=cw,
        callbacks=cb,
        verbose=0,
    )
    elapsed = time.perf_counter() - t0
    y_prob = model.predict(x_va, verbose=0).reshape(-1)
    out_path = NASNET_ARTIFACTS_DIR / f"mlp_baseline_seed_{seed}.keras"
    model.save(out_path)
    np.save(NASNET_ARTIFACTS_DIR / f"mlp_val_prob_seed_{seed}.npy", y_prob)
    return {
        "seed": seed,
        "best_val_pr_auc": float(max(hist.history.get("val_pr_auc", [float("nan")]))),
        "training_time_sec": elapsed,
        "checkpoint": str(out_path),
        "y_prob_path": str(NASNET_ARTIFACTS_DIR / f"mlp_val_prob_seed_{seed}.npy"),
    }
