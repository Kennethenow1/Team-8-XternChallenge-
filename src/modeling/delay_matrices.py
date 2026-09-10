"""Train-only delay matrices under data/gold/delay/modeling/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from src.common.paths import GOLD_DIR, SILVER_DIR
from src.gold.cod_delay import FOLLOWUP_MONTHS
from src.modeling.delay_feature_policy import META, NATIVE_CATEGORICALS, SEQ_CHANNELS, delay_feature_lists

DELAY_DIR = GOLD_DIR / "delay"
MODELING_DIR = DELAY_DIR / "modeling"
ARTIFACTS = MODELING_DIR / "artifacts"
SPLITS = ("train", "val", "test", "score")
SEQ_T = 12


def _supervised_mask(df: pd.DataFrame, split: str) -> pd.Series:
    m = df["split"].astype(str).eq(split)
    if split == "score":
        return m
    return m & df["cod_slip_months_next_12m"].notna() & df["complete_followup"].fillna(False)


def _meta_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        c
        for c in (
            "project_key",
            "observation_date",
            "cod_slip_months_next_12m",
            "cod_slip_ge_12m",
            "event_type",
            "capacity_mw",
            "complete_followup",
            "is_gia",
            "service_date_shift_months",
            "cod_at_t",
            "study_phase",
            "post_gia_status",
            "transmission_owner",
        )
        if c in df.columns
    ]
    return df[cols].copy()


def prepare_delay_matrices() -> dict[str, Any]:
    MODELING_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(DELAY_DIR / "cod_delay_panel.parquet")
    lists = delay_feature_lists(panel)
    cats, nums = lists["categorical_columns"], lists["numeric_columns"]

    slices: dict[str, pd.DataFrame] = {}
    for split in SPLITS:
        part = panel.loc[_supervised_mask(panel, split)].copy()
        slices[split] = part
        part.to_parquet(MODELING_DIR / f"delay_panel_{split}.parquet", index=False)

    train = slices["train"]
    # --- logistic: impute + scale + one-hot ---
    nums = [c for c in nums if c in train.columns and pd.to_numeric(train[c], errors="coerce").notna().any()]
    (ARTIFACTS / "feature_columns.json").write_text(json.dumps({"categorical_columns": cats, "numeric_columns": nums, "feature_columns": cats + nums, "n": len(cats) + len(nums)}, indent=2), encoding="utf-8")
    train_num = train[nums].apply(pd.to_numeric, errors="coerce") if nums else pd.DataFrame(index=train.index)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    if nums:
        xtr = imputer.fit_transform(train_num)
        xtr = scaler.fit_transform(xtr)
    else:
        xtr = np.zeros((len(train), 0))
    joblib.dump({"imputer": imputer, "scaler": scaler, "numeric_columns": nums, "categorical_columns": cats}, ARTIFACTS / "logistic_transformers.joblib")

    dummy_cols: list[str] | None = None
    paths: dict[str, Any] = {"logistic": {}, "tree": {}, "catboost": {}, "foundation": {}, "tabm": {}, "ftt": {}}
    for split, part in slices.items():
        meta = _meta_frame(part)
        # foundation / catboost native
        found = meta.copy()
        for c in cats:
            found[c] = part[c].astype("string") if c in part.columns else pd.NA
        for c in nums:
            found[c] = pd.to_numeric(part[c], errors="coerce") if c in part.columns else np.nan
        found.to_parquet(MODELING_DIR / f"delay_foundation_v1_{split}.parquet", index=False)
        paths["foundation"][split] = str(MODELING_DIR / f"delay_foundation_v1_{split}.parquet")
        cb = found.copy()
        for c in cats:
            if c in cb.columns:
                cb[c] = cb[c].astype("string").astype("category")
        cb.to_parquet(MODELING_DIR / f"delay_catboost_native_v1_{split}.parquet", index=False)
        paths["catboost"][split] = str(MODELING_DIR / f"delay_catboost_native_v1_{split}.parquet")

        # tree: one-hot, keep NaNs in numeric
        tree = meta.copy()
        for c in nums:
            tree[c] = pd.to_numeric(part[c], errors="coerce")
        if cats:
            dummies = pd.get_dummies(part[cats].astype("string").fillna("__MISSING__"), prefix=cats, dummy_na=False)
            if dummy_cols is None:
                dummy_cols = list(dummies.columns)
            dummies = dummies.reindex(columns=dummy_cols, fill_value=0)
            tree = pd.concat([tree.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
        tree.to_parquet(MODELING_DIR / f"delay_tree_v1_{split}.parquet", index=False)
        paths["tree"][split] = str(MODELING_DIR / f"delay_tree_v1_{split}.parquet")

        # logistic scaled
        log = meta.copy()
        if nums:
            xn = imputer.transform(part[nums].apply(pd.to_numeric, errors="coerce"))
            xn = scaler.transform(xn)
            for i, c in enumerate(nums):
                log[c] = xn[:, i]
        if cats:
            dummies = pd.get_dummies(part[cats].astype("string").fillna("__MISSING__"), prefix=cats, dummy_na=False)
            dummies = dummies.reindex(columns=dummy_cols or list(dummies.columns), fill_value=0)
            log = pd.concat([log.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
        log.to_parquet(MODELING_DIR / f"delay_logistic_v1_{split}.parquet", index=False)
        paths["logistic"][split] = str(MODELING_DIR / f"delay_logistic_v1_{split}.parquet")

    # tabm / ftt
    cat_maps: dict[str, dict[str, int]] = {}
    for c in cats:
        vals = train[c].astype("string").fillna("__MISSING__")
        uniq = sorted(vals.unique().tolist())
        cat_maps[c] = {v: i for i, v in enumerate(uniq)}
    tab_imputer = SimpleImputer(strategy="median")
    tab_scaler = StandardScaler()
    if nums:
        tab_imputer.fit(train[nums].apply(pd.to_numeric, errors="coerce"))
        tab_scaler.fit(tab_imputer.transform(train[nums].apply(pd.to_numeric, errors="coerce")))
    joblib.dump({"cat_maps": cat_maps, "imputer": tab_imputer, "scaler": tab_scaler, "numeric_columns": nums, "categorical_columns": cats}, ARTIFACTS / "tabm_transformers.joblib")

    for split, part in slices.items():
        meta = _meta_frame(part)
        out = meta.copy()
        for c in cats:
            m = cat_maps[c]
            unseen = max(m.values()) + 1 if m else 0
            s = part[c].astype("string").fillna("__MISSING__")
            out[c] = s.map(lambda x, _m=m, _u=unseen: _m.get(x, _u)).astype(np.int32)
        if nums:
            xn = tab_imputer.transform(part[nums].apply(pd.to_numeric, errors="coerce"))
            xn = tab_scaler.transform(xn)
            for i, c in enumerate(nums):
                out[c] = xn[:, i]
        out.to_parquet(MODELING_DIR / f"delay_tabm_v1_{split}.parquet", index=False)
        out.to_parquet(MODELING_DIR / f"delay_ftt_v1_{split}.parquet", index=False)
        paths["tabm"][split] = str(MODELING_DIR / f"delay_tabm_v1_{split}.parquet")
        paths["ftt"][split] = str(MODELING_DIR / f"delay_ftt_v1_{split}.parquet")

    seq = _write_sequences(panel, slices)
    paths["seq"] = seq
    summary = {
        "n_train_labeled": int(len(slices["train"])),
        "n_val_labeled": int(len(slices["val"])),
        "n_test_labeled": int(len(slices["test"])),
        "n_features_numeric": len(nums),
        "n_features_cat": len(cats),
        "paths": paths,
    }
    (ARTIFACTS / "matrix_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def _write_sequences(panel: pd.DataFrame, slices: dict[str, pd.DataFrame]) -> dict[str, str]:
    snaps_path = SILVER_DIR / "snapshots" / "project_snapshots.parquet"
    snaps = pd.read_parquet(snaps_path)
    snaps["observation_date"] = pd.to_datetime(snaps["observation_date"])
    snaps["proposed_service_date"] = pd.to_datetime(snaps["proposed_service_date"], errors="coerce")
    snaps["queue_date"] = pd.to_datetime(snaps["queue_date"], errors="coerce")
    snaps["capacity_mw"] = pd.to_numeric(snaps["capacity_mw"], errors="coerce")
    snaps["log1p_capacity_mw"] = np.log1p(snaps["capacity_mw"].clip(lower=0).fillna(0))
    snaps["queue_age_months"] = (snaps["observation_date"] - snaps["queue_date"]).dt.days / 30.4375
    snaps["months_until_service"] = (snaps["proposed_service_date"] - snaps["observation_date"]).dt.days / 30.4375
    snaps["service_date_shift_months"] = pd.to_numeric(snaps.get("service_date_shift_months"), errors="coerce")
    phase_map = {v: i + 1 for i, v in enumerate(sorted(snaps["study_phase"].dropna().astype(str).unique()))}
    snaps["_phase_id"] = snaps["study_phase"].astype("string").map(phase_map).fillna(0)

    channels = [c for c in SEQ_CHANNELS if c in snaps.columns or c in {"_phase_id"}]
    # always include phase id
    feat_names = ["queue_age_months", "log1p_capacity_mw", "months_until_service", "service_date_shift_months", "_phase_id"]
    by_key: dict[str, pd.DataFrame] = {k: g.sort_values("observation_date") for k, g in snaps.groupby("project_key")}
    paths: dict[str, str] = {}
    for split, part in slices.items():
        X = np.zeros((len(part), SEQ_T, len(feat_names)), dtype=np.float32)
        mask = np.zeros((len(part), SEQ_T), dtype=np.float32)
        y = pd.to_numeric(part["cod_slip_months_next_12m"], errors="coerce").to_numpy(dtype=np.float32)
        keys = part["project_key"].astype(str).to_numpy()
        dates = pd.to_datetime(part["observation_date"]).to_numpy()
        for i, (key, t) in enumerate(zip(keys, dates, strict=False)):
            g = by_key.get(key)
            if g is None:
                continue
            hist = g[g["observation_date"] <= pd.Timestamp(t)].tail(SEQ_T)
            n = len(hist)
            if n == 0:
                continue
            start = SEQ_T - n
            vals = hist[feat_names].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
            X[i, start:] = vals
            mask[i, start:] = 1.0
        path = MODELING_DIR / f"delay_seq_v1_{split}.npz"
        np.savez_compressed(path, X=X, mask=mask, y=y, project_key=keys.astype(object), observation_date=dates.astype("datetime64[ns]"), channels=np.array(feat_names))
        paths[split] = str(path)
    return paths


if __name__ == "__main__":
    print(json.dumps(prepare_delay_matrices(), indent=2, default=str))
