"""Leakage / sealed-path tests for NASNet experiment."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.nasnet import assert_not_sealed_path
from src.models.nasnet.preprocess_nasnet import fit_transform_features, build_feature_roles
import numpy as np
import pandas as pd


def test_sealed_paths_refused():
    with pytest.raises(RuntimeError, match="sealed"):
        assert_not_sealed_path(Path("data/gold/modeling/model_ready_test.parquet"))
    with pytest.raises(RuntimeError, match="sealed"):
        assert_not_sealed_path(Path("/tmp/model_ready_score.parquet"))


def test_val_does_not_change_train_medians():
    rng = np.random.default_rng(1)
    n = 100
    train = pd.DataFrame(
        {
            "project_key": [f"p{i}" for i in range(n)],
            "observation_date": pd.Timestamp("2021-01-01"),
            "withdraw_next_12m": rng.integers(0, 2, n),
            "num_a": np.arange(n, dtype=float),
            "flag": rng.integers(0, 2, n).astype(float),
        }
    )
    val = train.copy()
    val["num_a"] = np.arange(n, dtype=float) + 1000.0  # shift VAL hugely
    meta = build_feature_roles(train, target="withdraw_next_12m")
    _, _, art1 = fit_transform_features(train, val, meta)
    # Replace VAL with zeros — medians must stay identical
    val2 = train.copy()
    val2["num_a"] = 0.0
    _, _, art2 = fit_transform_features(train, val2, meta)
    assert art1["numeric_medians"] == art2["numeric_medians"]
    assert art1["numeric_clip_bounds"] == art2["numeric_clip_bounds"]
