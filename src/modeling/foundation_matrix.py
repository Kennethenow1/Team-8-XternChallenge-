"""Build foundation_ready / foundation_v1 matrices for tabular foundation models.

Native categoricals; NaNs retained; no StandardScaler / one-hot.
Does not modify enriched Gold panels. Does not fit models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.paths import GOLD_DIR
from src.modeling.feature_policy import HARD_DROPS, META

MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_DIR = MODELING_DIR / "artifacts"
SPLITS = ("train", "val", "test", "score")

# Restored as string/category columns for TFMs
NATIVE_CATEGORICALS = (
    "technology_primary",
    "state_code",
    "study_phase",
    "service_type",
)

PANEL_PATH = GOLD_DIR / "withdrawal_panel_enriched.parquet"
SCORE_PANEL_PATH = GOLD_DIR / "current_miso_scoring_enriched.parquet"


def _is_onehot_for_cat(col: str, cat: str) -> bool:
    return col == f"{cat}_missing" or col.startswith(f"{cat}__")


def onehot_columns_to_drop(columns: list[str], cats: tuple[str, ...] = NATIVE_CATEGORICALS) -> list[str]:
    drop: list[str] = []
    for c in columns:
        for cat in cats:
            if _is_onehot_for_cat(c, cat):
                drop.append(c)
                break
    return list(dict.fromkeys(drop))


def _load_category_lookup() -> pd.DataFrame:
    """Project×date → native categoricals from enriched panels (read-only)."""
    import pyarrow.parquet as pq

    frames: list[pd.DataFrame] = []
    keep = ["project_key", "observation_date", *NATIVE_CATEGORICALS]
    for path in (PANEL_PATH, SCORE_PANEL_PATH):
        if not path.exists():
            continue
        schema_names = set(pq.read_schema(path).names)
        use = [c for c in keep if c in schema_names]
        df = pd.read_parquet(path, columns=use)
        for c in keep:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[list(keep)].copy()
        df["observation_date"] = pd.to_datetime(df["observation_date"])
        frames.append(df)
    if not frames:
        raise FileNotFoundError("Need withdrawal_panel_enriched and/or current_miso_scoring_enriched")
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["project_key", "observation_date"], keep="last")
    return out


def build_foundation_frame(model_ready: pd.DataFrame, cat_lookup: pd.DataFrame) -> pd.DataFrame:
    """Replace one-hot cat blocks with native categoricals; keep NaNs; no scaling."""
    df = model_ready.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    x_cols = [c for c in df.columns if c not in META]
    drop_oh = onehot_columns_to_drop(x_cols)
    df = df.drop(columns=[c for c in drop_oh if c in df.columns], errors="ignore")

    cats = cat_lookup.copy()
    merged = df.merge(cats, on=["project_key", "observation_date"], how="left", suffixes=("", "_panel"))
    for cat in NATIVE_CATEGORICALS:
        panel_col = f"{cat}_panel"
        if panel_col in merged.columns:
            if cat in merged.columns:
                merged[cat] = merged[cat].fillna(merged[panel_col])
                merged = merged.drop(columns=[panel_col])
            else:
                merged = merged.rename(columns={panel_col: cat})
        elif cat not in merged.columns:
            merged[cat] = pd.NA

    # Prefer string dtype for TFM categorical detection
    for cat in NATIVE_CATEGORICALS:
        if cat in merged.columns:
            merged[cat] = merged[cat].astype("string")

    return merged


def apply_foundation_v1_policy(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Same semantic HARD_DROPS as logistic/tree V1; no reference-dummy drops."""
    x_cols = [c for c in df.columns if c not in META]
    drops = [c for c in HARD_DROPS if c in x_cols]
    # Constant missing/available indicators on this frame (train should drive this;
    # caller passes train-derived drop list for consistency across splits).
    for c in x_cols:
        if c in drops:
            continue
        if c.endswith("_missing") or c.endswith("_available"):
            if c in NATIVE_CATEGORICALS:
                continue
            nunq = int(pd.to_numeric(df[c], errors="coerce").nunique(dropna=True))
            if nunq <= 1:
                drops.append(c)
    drops = list(dict.fromkeys(drops))
    keep_x = [c for c in x_cols if c not in drops]
    meta_present = [c for c in ("project_key", "observation_date", "withdraw_next_12m") if c in df.columns]
    out = df[meta_present + keep_x].copy()
    return out, keep_x


def foundation_column_lists(feature_columns: list[str]) -> dict[str, list[str]]:
    categorical = [c for c in NATIVE_CATEGORICALS if c in feature_columns]
    numeric = [c for c in feature_columns if c not in categorical]
    return {
        "feature_columns": feature_columns,
        "categorical_columns": categorical,
        "numeric_columns": numeric,
    }


def run_foundation_matrices(
    modeling_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    modeling_dir = modeling_dir or MODELING_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    cat_lookup = _load_category_lookup()
    paths: dict[str, Any] = {"foundation_ready": {}, "foundation_v1": {}}

    train_src = modeling_dir / "model_ready_train.parquet"
    if not train_src.exists():
        raise FileNotFoundError(f"Missing {train_src}")

    train_ready = build_foundation_frame(pd.read_parquet(train_src), cat_lookup)
    # Fix V1 drops from train foundation_ready (stable across splits)
    train_drops = [c for c in HARD_DROPS if c in train_ready.columns]
    for c in [x for x in train_ready.columns if x not in META]:
        if c in train_drops or c in NATIVE_CATEGORICALS:
            continue
        if c.endswith("_missing") or c.endswith("_available"):
            if int(pd.to_numeric(train_ready[c], errors="coerce").nunique(dropna=True)) <= 1:
                train_drops.append(c)
    train_drops = list(dict.fromkeys(train_drops))

    v1_feature_cols: list[str] | None = None

    for split in SPLITS:
        src = modeling_dir / f"model_ready_{split}.parquet"
        if not src.exists():
            continue
        ready = build_foundation_frame(pd.read_parquet(src), cat_lookup)
        ready_path = modeling_dir / f"foundation_ready_{split}.parquet"
        ready.to_parquet(ready_path, index=False)
        paths["foundation_ready"][split] = str(ready_path)

        x_cols = [c for c in ready.columns if c not in META]
        keep_x = [c for c in x_cols if c not in train_drops]
        meta_present = [c for c in ("project_key", "observation_date", "withdraw_next_12m") if c in ready.columns]
        v1 = ready[meta_present + keep_x].copy()
        v1_path = modeling_dir / f"foundation_v1_{split}.parquet"
        v1.to_parquet(v1_path, index=False)
        paths["foundation_v1"][split] = str(v1_path)
        if split == "train":
            v1_feature_cols = keep_x

    assert v1_feature_cols is not None
    col_lists = foundation_column_lists(v1_feature_cols)
    cols_path = artifacts_dir / "feature_columns_foundation_v1.json"
    cols_path.write_text(
        json.dumps(
            {
                **col_lists,
                "n": len(v1_feature_cols),
                "n_categorical": len(col_lists["categorical_columns"]),
                "n_numeric": len(col_lists["numeric_columns"]),
                "policy": "foundation_v1",
                "dropped": train_drops,
                "notes": [
                    "Native categoricals restored from enriched panel; one-hot cat blocks removed.",
                    "No imputation or StandardScaler.",
                    "Same HARD_DROPS semantics as V1; no reference dummy drops.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Sanity: no leftover one-hots for native cats
    leftover = onehot_columns_to_drop(v1_feature_cols)
    return {
        "paths": paths,
        "n_foundation_v1_features": len(v1_feature_cols),
        "feature_columns_path": str(cols_path),
        "dropped": train_drops,
        "categorical_columns": col_lists["categorical_columns"],
        "leftover_onehots": leftover,
        "columns": col_lists,
    }
