"""NASNetLarge tabular-to-image delay regressor. Full budget: 100 frozen + 20 finetune. GPU required."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.common.paths import REPO_ROOT
from src.modeling.delay.common import labeled_mask, pack_metrics
from src.modeling.delay.registry import load_xy
from src.modeling.delay_eval_protocol import neural_nets_allowed
from src.modeling.eval_protocol import SELECTION_SPLIT, assert_selection_split
from src.models.nasnet.build_nasnet_dataset import grid_side, make_tf_dataset
from src.models.nasnet.train_nasnetlarge import (
    enable_mixed_precision,
    require_gpu,
    set_global_seed,
    unfreeze_last_nasnet_cell,
)


def load_delay_nasnet_config() -> dict[str, Any]:
    path = REPO_ROOT / "configs" / "nasnet_delay.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_nasnet_delay_model(*, l2: float, dense_256: int, dense_64: int, dropout_1: float, dropout_2: float):
    import tensorflow as tf

    base = tf.keras.applications.NASNetLarge(
        include_top=False, weights="imagenet", input_shape=(331, 331, 3), pooling="avg"
    )
    base.trainable = False
    reg = tf.keras.regularizers.l2(l2)
    inputs = tf.keras.Input(shape=(331, 331, 3), name="image")
    x = base(inputs, training=False)
    x = tf.keras.layers.BatchNormalization(name="head_bn")(x)
    x = tf.keras.layers.Dense(dense_256, activation="relu", kernel_regularizer=reg)(x)
    x = tf.keras.layers.Dropout(dropout_1)(x)
    x = tf.keras.layers.Dense(dense_64, activation="relu", kernel_regularizer=reg)(x)
    x = tf.keras.layers.Dropout(dropout_2)(x)
    outputs = tf.keras.layers.Dense(1, activation="linear", dtype="float32", name="delay_months")(x)
    model = tf.keras.Model(inputs, outputs, name="nasnetlarge_delay")
    model.base_model = base  # type: ignore[attr-defined]
    return model


def fit_nasnet_delay(
    *,
    seed: int = 42,
    model_name: str = "nasnet_cnn",
    do_finetune: bool | None = None,
) -> dict[str, Any]:
    assert_selection_split(SELECTION_SPLIT)
    if not neural_nets_allowed():
        return {"model": model_name, "status": "skipped", "reason": "insufficient_n: val labeled < 200"}
    cfg = load_delay_nasnet_config()
    tcfg = cfg.get("training", {})
    try:
        hw = require_gpu(require=bool(tcfg.get("require_gpu", True)))
    except RuntimeError as e:
        return {"model": model_name, "status": "skipped", "reason": str(e)}
    set_global_seed(seed)
    enable_mixed_precision()

    X_tr, y_tr, _ = load_xy("delay_logistic_v1", "train")
    X_va, y_va, meta_va = load_xy("delay_logistic_v1", SELECTION_SPLIT)
    mtr, mva = labeled_mask(y_tr), labeled_mask(y_va)
    X_tr, y_tr = X_tr.loc[mtr].apply(pd.to_numeric, errors="coerce").fillna(0.0), y_tr.loc[mtr]
    X_va, y_va, meta_va = X_va.loc[mva].apply(pd.to_numeric, errors="coerce").fillna(0.0), y_va.loc[mva], meta_va.loc[mva]
    x_tr = X_tr.to_numpy(np.float32)
    x_va = X_va.to_numpy(np.float32)
    ytr = y_tr.astype(np.float32).to_numpy()
    yva = y_va.astype(np.float32).to_numpy()
    side = grid_side(x_tr.shape[1])
    import tensorflow as tf

    candidates = [int(x) for x in tcfg.get("batch_size_candidates", [8, 4, 2])]
    batch = int(tcfg.get("batch_size", candidates[0]))
    if batch not in candidates:
        candidates = [batch, *candidates]
    frozen_epochs = int(tcfg.get("frozen_epochs", 100))
    do_ft = tcfg.get("do_finetune", True) if do_finetune is None else bool(do_finetune)
    model = None
    ds_tr = ds_va = None
    hist_f = hist_ft = None
    extra_note = "finetune off"
    last_err = None
    for batch in candidates:
        try:
            tf.keras.backend.clear_session()
            model = build_nasnet_delay_model(
                l2=float(tcfg.get("l2", 1e-4)),
                dense_256=int(tcfg.get("dense_256", 256)),
                dense_64=int(tcfg.get("dense_64", 64)),
                dropout_1=float(tcfg.get("dropout_1", 0.5)),
                dropout_2=float(tcfg.get("dropout_2", 0.3)),
            )
            model.compile(
                optimizer=tf.keras.optimizers.Adam(float(tcfg.get("learning_rate", 1e-4))),
                loss=tf.keras.losses.Huber(delta=12.0),
                metrics=[tf.keras.metrics.MeanAbsoluteError(name="mae")],
            )
            ds_tr = make_tf_dataset(x_tr, ytr, side=side, batch_size=batch, shuffle=True, seed=seed)
            ds_va = make_tf_dataset(x_va, yva, side=side, batch_size=batch, shuffle=False)
            _ = model.predict(ds_va.take(1), verbose=0)
            print(f"[nasnet_delay] batch_size={batch} starting frozen fit", flush=True)
            cbs = [
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_mae",
                    patience=int(tcfg.get("early_stopping_patience", 8)),
                    mode="min",
                    restore_best_weights=True,
                ),
                tf.keras.callbacks.ReduceLROnPlateau(
                    monitor="val_mae",
                    patience=int(tcfg.get("reduce_lr_patience", 3)),
                    factor=0.5,
                    min_lr=1e-7,
                    mode="min",
                ),
            ]
            hist_f = model.fit(ds_tr, validation_data=ds_va, epochs=frozen_epochs, callbacks=cbs, verbose=2)
            extra_note = "finetune off"
            hist_ft = None
            if do_ft:
                try:
                    n_un = unfreeze_last_nasnet_cell(model.base_model)
                    model.compile(
                        optimizer=tf.keras.optimizers.Adam(float(tcfg.get("finetune_learning_rate", 1e-6))),
                        loss=tf.keras.losses.Huber(delta=12.0),
                        metrics=[tf.keras.metrics.MeanAbsoluteError(name="mae")],
                    )
                    hist_ft = model.fit(
                        ds_tr,
                        validation_data=ds_va,
                        epochs=int(tcfg.get("finetune_epochs", 20)),
                        callbacks=cbs,
                        verbose=2,
                    )
                    extra_note = f"unfroze {n_un} layers"
                except Exception as e:  # noqa: BLE001
                    print(f"[nasnet_delay] finetune failed at batch={batch}: {e}; keeping frozen weights", flush=True)
                    extra_note = f"finetune failed ({type(e).__name__}); kept frozen"
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[nasnet_delay] batch_size={batch} failed: {e}", flush=True)
            tf.keras.backend.clear_session()
            model = None
            hist_f = None
    if model is None or ds_tr is None or hist_f is None:
        return {"model": model_name, "status": "skipped", "reason": f"NASNet OOM/init failed: {last_err}"}
    n_frozen = len(hist_f.history.get("loss", []))

    pred = model.predict(ds_va, verbose=0).reshape(-1)
    history = []
    for i, (tr, va) in enumerate(zip(hist_f.history.get("loss", []), hist_f.history.get("val_mae", hist_f.history.get("val_loss", [])), strict=False)):
        history.append({"step": float(i), "train_loss": float(tr), "val_mae": float(va), "val_loss": float(va), "phase": "frozen"})
    if hist_ft is not None:
        off = len(history)
        for i, (tr, va) in enumerate(zip(hist_ft.history.get("loss", []), hist_ft.history.get("val_mae", hist_ft.history.get("val_loss", [])), strict=False)):
            history.append({"step": float(off + i), "train_loss": float(tr), "val_mae": float(va), "val_loss": float(va), "phase": "finetune"})

    stopped_on_patience = n_frozen < frozen_epochs
    if n_frozen < 8 and not stopped_on_patience:
        return {"model": model_name, "status": "skipped", "reason": f"refusing ok status: frozen epochs={n_frozen} < 8 without patience hit"}

    extra = {
        "n_features": int(x_tr.shape[1]),
        "n_frozen_epochs": n_frozen,
        "hardware": hw,
        "note": extra_note,
        "_model": model,
    }
    return pack_metrics(model=model_name, y_va=y_va, pred=pred, meta_va=meta_va, history=history, extra=extra)
