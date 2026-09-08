"""On-demand tabular → 331×331×3 image tf.data pipeline for NASNetLarge."""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
import pandas as pd


def grid_side(n_features: int) -> int:
    return int(math.ceil(math.sqrt(n_features)))


def vector_to_grid(vector: np.ndarray, *, side: int) -> np.ndarray:
    """Place features row-major into side×side grid; pad unused with 0."""
    v = np.asarray(vector, dtype=np.float32).reshape(-1)
    grid = np.zeros((side, side), dtype=np.float32)
    n = min(len(v), side * side)
    if n:
        grid.flat[:n] = v[:n]
    return grid


def grid_to_rgb_image(grid: np.ndarray, *, target_size: int = 331) -> np.ndarray:
    """Replicate grid to 3 channels and nearest-neighbor resize to target_size."""
    import tensorflow as tf

    g = tf.convert_to_tensor(grid, dtype=tf.float32)
    if g.shape.rank == 2:
        g = g[..., None]
    rgb = tf.repeat(g, repeats=3, axis=-1)  # H,W,3
    rgb = rgb[None, ...]  # 1,H,W,3
    out = tf.image.resize(rgb, [target_size, target_size], method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
    return out[0]


def make_tf_dataset(
    features: np.ndarray,
    labels: np.ndarray | None,
    *,
    side: int,
    target_size: int = 331,
    batch_size: int = 4,
    shuffle: bool = False,
    shuffle_buffer: int = 1024,
    seed: int = 42,
    drop_remainder: bool = False,
) -> Any:
    """Build tf.data.Dataset that constructs images on the fly (no materialized 331 arrays)."""
    import tensorflow as tf

    x = np.asarray(features, dtype=np.float32)
    if labels is None:
        y = np.zeros((len(x),), dtype=np.float32)
        has_labels = False
    else:
        y = np.asarray(labels, dtype=np.float32).reshape(-1)
        has_labels = True

    ds = tf.data.Dataset.from_tensor_slices((x, y))
    if shuffle:
        ds = ds.shuffle(buffer_size=min(shuffle_buffer, len(x)), seed=seed, reshuffle_each_iteration=True)

    def _map(vec, lab):
        flat = tf.reshape(tf.cast(vec, tf.float32), [-1])
        n = tf.shape(flat)[0]
        pad_n = side * side - n
        padded = tf.cond(
            pad_n > 0,
            lambda: tf.concat([flat, tf.zeros([pad_n], dtype=tf.float32)], axis=0),
            lambda: flat[: side * side],
        )
        grid = tf.reshape(padded, [side, side])
        rgb = tf.repeat(grid[..., None], repeats=3, axis=-1)
        img = tf.image.resize(
            rgb[None, ...],
            [target_size, target_size],
            method=tf.image.ResizeMethod.NEAREST_NEIGHBOR,
        )[0]
        img = tf.cast(img, tf.float32)
        lab = tf.reshape(tf.cast(lab, tf.float32), [1])
        return img, lab

    ds = ds.map(_map, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size, drop_remainder=drop_remainder)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    ds.has_labels = has_labels  # type: ignore[attr-defined]
    return ds


def matrices_to_xy(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
    target: str,
) -> tuple[np.ndarray, np.ndarray]:
    x = df.loc[:, list(feature_columns)].to_numpy(dtype=np.float32)
    y = pd.to_numeric(df[target], errors="coerce").to_numpy(dtype=np.float32)
    return x, y


def example_encoding_arrays(
    vector: np.ndarray,
    *,
    side: int,
    target_size: int = 331,
) -> dict[str, np.ndarray]:
    """CPU-side diagnostic grids for audit plots (small)."""
    grid = vector_to_grid(vector, side=side)
    pad_mask = np.zeros((side, side), dtype=bool)
    n = min(len(np.asarray(vector).reshape(-1)), side * side)
    pad_mask.flat[n:] = True
    # Nearest resize without TF for audit if TF unavailable
    try:
        img = grid_to_rgb_image(grid, target_size=target_size).numpy()
    except Exception:
        # fallback: block upsample
        reps = max(1, target_size // side)
        block = np.repeat(np.repeat(grid, reps, axis=0), reps, axis=1)
        block = block[:target_size, :target_size]
        if block.shape[0] < target_size or block.shape[1] < target_size:
            out = np.zeros((target_size, target_size), dtype=np.float32)
            out[: block.shape[0], : block.shape[1]] = block
            block = out
        img = np.stack([block, block, block], axis=-1)
    return {"raw_grid": grid, "padding_mask": pad_mask, "resized_rgb": img}
