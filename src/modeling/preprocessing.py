"""Train-only imputation + scaling for logistic path; leave NaNs for trees.

Does not fit models. Fit transformers on model_ready_train only; apply to val/test/score.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from src.common.paths import GOLD_DIR, QUALITY_DIR
from src.modeling.feature_analysis import build_model_ready_schema_report
from src.modeling.feature_policy import build_v1_feature_policy, write_v1_policy
from src.modeling.foundation_matrix import run_foundation_matrices
from src.modeling.tabm_matrix import run_catboost_and_tabm_matrices
from src.modeling.eval_protocol import write_protocol_notes

MODELING_DIR = GOLD_DIR / "modeling"
ARTIFACTS_DIR = MODELING_DIR / "artifacts"
REPORT_DIR = QUALITY_DIR / "modeling"
SPLITS = ("train", "val", "test", "score")
META_COLS = ("project_key", "observation_date", "withdraw_next_12m")
SPARSE_MISSING_PCT = 80.0


def _load_schema(schema_path: Path | None = None) -> pd.DataFrame:
    path = schema_path or (REPORT_DIR / "model_ready_schema.csv")
    if path.exists():
        return pd.read_csv(path)
    train = pd.read_parquet(MODELING_DIR / "model_ready_train.parquet")
    return build_model_ready_schema_report(train)


def feature_column_lists(schema: pd.DataFrame, train: pd.DataFrame | None = None) -> dict[str, list[str]]:
    """Partition columns for X construction."""
    x_roles = {"numeric", "binary", "onehot", "missing_indicator"}
    feat = schema[schema["role"].isin(x_roles)]["feature"].tolist()
    scale_cols = schema[(schema["feature"].isin(feat)) & (schema["scaling"] == "Yes*")]["feature"].tolist()
    # Logistic safety: median-impute all X columns using train statistics so
    # val/test/score NaNs in columns that were complete on train still get filled.
    impute_cols = list(feat)
    return {
        "feature_columns": feat,
        "scale_columns": scale_cols,
        "impute_columns": impute_cols,
    }


def write_sparse_feature_flags(schema: pd.DataFrame, report_dir: Path | None = None) -> dict[str, Any]:
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    sparse = schema[
        (schema["role"] == "numeric") & (schema["missing_pct"] >= SPARSE_MISSING_PCT)
    ].copy()
    sparse["ablation_candidate"] = True

    train_path = MODELING_DIR / "model_ready_train.parquet"
    if train_path.exists():
        tr = pd.read_parquet(train_path)
        n = len(tr)
        sparse["n_non_null"] = [
            int(tr[c].notna().sum()) if c in tr.columns else None for c in sparse["feature"]
        ]
        sparse["n_rows"] = n
    else:
        sparse["n_non_null"] = None
        sparse["n_rows"] = None

    csv_path = report_dir / "sparse_feature_flags.csv"
    sparse.to_csv(csv_path, index=False)

    lines = [
        "# Sparse feature flags (ablation candidates)",
        "",
        f"Numeric features with missing ≥ **{SPARSE_MISSING_PCT:.0f}%** on train `model_ready`.",
        "Do **not** auto-drop. Protocol: **Model A** with feature, **Model B** without — compare **validation** metrics.",
        "",
        "## Callout: `years_since_last_change`",
        "",
    ]
    y = sparse[sparse["feature"] == "years_since_last_change"]
    if len(y):
        row = y.iloc[0]
        lines.extend(
            [
                f"- missing %: **{row['missing_pct']}**",
                f"- non-null train rows: **{row.get('n_non_null', '?')}**",
                "- Extremely sparse — test with vs without on validation before keeping.",
                "",
            ]
        )
    else:
        lines.append("_Not present or below threshold._\n")

    lines.extend(["## All sparse numerics", "", "| feature | missing % | n_non_null |", "|---------|-----------|------------|"])
    for _, r in sparse.sort_values("missing_pct", ascending=False).iterrows():
        lines.append(f"| `{r['feature']}` | {r['missing_pct']} | {r.get('n_non_null', '')} |")
    lines.append("")
    md_path = report_dir / "sparse_feature_flags.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "n_sparse": int(len(sparse)),
        "features": sparse["feature"].tolist(),
        "csv": str(csv_path),
        "md": str(md_path),
    }


def _meta_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in META_COLS if c in df.columns]
    return df[cols].copy()


def fit_logistic_transformers(
    train: pd.DataFrame,
    feature_columns: list[str],
    impute_columns: list[str],
    scale_columns: list[str],
) -> dict[str, Any]:
    X = train[feature_columns].apply(pd.to_numeric, errors="coerce")
    impute_cols = [c for c in impute_columns if c in X.columns]
    scale_cols = [c for c in scale_columns if c in X.columns]

    imputer = SimpleImputer(strategy="median")
    if impute_cols:
        imputer.fit(X[impute_cols])
    else:
        imputer.fit(np.zeros((len(X), 1)))

    # After impute for scale fit
    X_imp = X.copy()
    if impute_cols:
        X_imp[impute_cols] = imputer.transform(X[impute_cols])

    scaler = StandardScaler()
    if scale_cols:
        scaler.fit(X_imp[scale_cols])
    else:
        scaler.fit(np.zeros((len(X), 1)))

    return {
        "imputer": imputer,
        "scaler": scaler,
        "feature_columns": feature_columns,
        "impute_columns": impute_cols,
        "scale_columns": scale_cols,
    }


def transform_logistic(df: pd.DataFrame, arts: dict[str, Any]) -> pd.DataFrame:
    feat = arts["feature_columns"]
    X = df[feat].apply(pd.to_numeric, errors="coerce")
    impute_cols = arts["impute_columns"]
    scale_cols = arts["scale_columns"]
    if impute_cols:
        X[impute_cols] = arts["imputer"].transform(X[impute_cols])
    if scale_cols:
        X[scale_cols] = arts["scaler"].transform(X[scale_cols])
    out = _meta_frame(df)
    for c in feat:
        out[c] = X[c].to_numpy()
    return out


def transform_tree(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Same X column order; leave NaNs; no scaling."""
    out = _meta_frame(df)
    X = df[feature_columns].apply(pd.to_numeric, errors="coerce")
    for c in feature_columns:
        out[c] = X[c].to_numpy()
    return out


def _subset_v1(df: pd.DataFrame, v1_cols: list[str]) -> pd.DataFrame:
    meta = _meta_frame(df)
    cols = [c for c in v1_cols if c in df.columns]
    out = meta.copy()
    for c in cols:
        out[c] = df[c].to_numpy()
    return out


def run_preprocessing(
    modeling_dir: Path | None = None,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    modeling_dir = modeling_dir or MODELING_DIR
    report_dir = report_dir or REPORT_DIR
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    schema = _load_schema(report_dir / "model_ready_schema.csv")
    sparse_info = write_sparse_feature_flags(schema, report_dir)

    train_path = modeling_dir / "model_ready_train.parquet"
    if not train_path.exists():
        raise FileNotFoundError(f"Missing {train_path}; run feature engineering first.")

    train = pd.read_parquet(train_path)
    cols = feature_column_lists(schema, train)
    arts = fit_logistic_transformers(
        train,
        cols["feature_columns"],
        cols["impute_columns"],
        cols["scale_columns"],
    )

    policy = build_v1_feature_policy(train, schema)
    policy_paths = write_v1_policy(policy, ARTIFACTS_DIR, report_dir)
    v1_cols = policy["feature_columns_v1"]

    joblib.dump(arts["imputer"], ARTIFACTS_DIR / "imputer.joblib")
    joblib.dump(arts["scaler"], ARTIFACTS_DIR / "scaler.joblib")
    (ARTIFACTS_DIR / "feature_columns.json").write_text(
        json.dumps(
            {
                "feature_columns": arts["feature_columns"],
                "impute_columns": arts["impute_columns"],
                "scale_columns": arts["scale_columns"],
                "fit_on": "model_ready_train",
                "imputer": "SimpleImputer(strategy=median)",
                "scaler": "StandardScaler",
                "notes": [
                    "Fit on train only; apply to val/test/score.",
                    "Missing/availability indicators kept; not imputed as targets.",
                    "Trees use tree_ready_* (NaNs retained, no scale).",
                    "V1 column subset: feature_columns_v1.json / logistic_v1_* / tree_v1_*.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    paths: dict[str, Any] = {
        "logistic": {},
        "tree": {},
        "logistic_v1": {},
        "tree_v1": {},
    }
    nan_check: dict[str, Any] = {}

    for split in SPLITS:
        src = modeling_dir / f"model_ready_{split}.parquet"
        if not src.exists():
            continue
        df = pd.read_parquet(src)
        log_df = transform_logistic(df, arts)
        tree_df = transform_tree(df, arts["feature_columns"])

        log_path = modeling_dir / f"logistic_ready_{split}.parquet"
        tree_path = modeling_dir / f"tree_ready_{split}.parquet"
        log_df.to_parquet(log_path, index=False)
        tree_df.to_parquet(tree_path, index=False)
        paths["logistic"][split] = str(log_path)
        paths["tree"][split] = str(tree_path)

        log_v1 = _subset_v1(log_df, v1_cols)
        tree_v1 = _subset_v1(tree_df, v1_cols)
        log_v1_path = modeling_dir / f"logistic_v1_{split}.parquet"
        tree_v1_path = modeling_dir / f"tree_v1_{split}.parquet"
        log_v1.to_parquet(log_v1_path, index=False)
        tree_v1.to_parquet(tree_v1_path, index=False)
        paths["logistic_v1"][split] = str(log_v1_path)
        paths["tree_v1"][split] = str(tree_v1_path)

        x_nan = float(log_df[arts["feature_columns"]].isna().any().any())
        v1_present = [c for c in v1_cols if c in log_v1.columns]
        nan_check[split] = {
            "logistic_X_has_nan": bool(x_nan),
            "logistic_v1_X_has_nan": bool(log_v1[v1_present].isna().any().any()),
            "tree_X_nan_frac": float(tree_df[arts["feature_columns"]].isna().mean().mean()),
            "n_rows": int(len(df)),
            "n_v1_features": len(v1_present),
        }

    foundation_info = run_foundation_matrices(modeling_dir, ARTIFACTS_DIR)
    paths["foundation_ready"] = foundation_info["paths"]["foundation_ready"]
    paths["foundation_v1"] = foundation_info["paths"]["foundation_v1"]
    extra = run_catboost_and_tabm_matrices(modeling_dir, ARTIFACTS_DIR)
    paths["catboost_native_v1"] = extra["catboost_native"]["paths"]
    paths["tabm_v1"] = extra["tabm"]["paths"]
    paths["ftt_v1"] = extra["ftt"]["paths"]
    protocol_path = write_protocol_notes(report_dir)

    summary = {
        "artifacts_dir": str(ARTIFACTS_DIR),
        "paths": paths,
        "nan_check": nan_check,
        "n_features": len(arts["feature_columns"]),
        "n_features_v1": len(v1_cols),
        "n_features_foundation_v1": foundation_info["n_foundation_v1_features"],
        "n_features_catboost_native_v1": extra["catboost_native"]["n_features"],
        "n_features_tabm_v1": extra["tabm"]["n_features"],
        "n_features_ftt_v1": extra["ftt"]["n_features"],
        "n_impute": len(arts["impute_columns"]),
        "n_scale": len(arts["scale_columns"]),
        "sparse_flags": sparse_info,
        "feature_policy_v1": policy_paths,
        "v1_dropped": policy["dropped_from_default"],
        "foundation": {
            "n_features": foundation_info["n_foundation_v1_features"],
            "categorical_columns": foundation_info["categorical_columns"],
            "dropped": foundation_info["dropped"],
            "leftover_onehots": foundation_info["leftover_onehots"],
            "feature_columns_path": foundation_info["feature_columns_path"],
        },
        "catboost_native": {
            "n_features": extra["catboost_native"]["n_features"],
            "categorical_columns": extra["catboost_native"]["categorical_columns"],
            "feature_columns_path": extra["catboost_native"]["feature_columns_path"],
        },
        "tabm": {
            "n_features": extra["tabm"]["n_features"],
            "categorical_columns": extra["tabm"]["categorical_columns"],
            "feature_columns_path": extra["tabm"]["feature_columns_path"],
            "transformers_path": extra["tabm"]["transformers_path"],
        },
        "ftt": {
            "n_features": extra["ftt"]["n_features"],
            "categorical_columns": extra["ftt"]["categorical_columns"],
            "feature_columns_path": extra["ftt"]["feature_columns_path"],
            "transformers_path": extra["ftt"]["transformers_path"],
        },
        "eval_protocol_md": str(protocol_path),
    }
    (report_dir / "preprocessing_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    (report_dir / "preprocessing_notes.md").write_text(
        "\n".join(
            [
                "# Preprocessing notes (train-only)",
                "",
                "## Five model-specific paths",
                "",
                "| Path | Role |",
                "|------|------|",
                "| `logistic_v1_*` | Median impute + StandardScaler + one-hot |",
                "| `tree_v1_*` | NaNs + one-hot (XGBoost) |",
                "| `catboost_native_v1_*` | Native cats; numeric NaNs; no scale |",
                "| `foundation_v1_*` | Native cats for TabICL / TabPFN; no external scale |",
                "| `tabm_v1_*` | Int cats + median impute + scale numerics |",
                "| `ftt_v1_*` | Alias of tabm_v1 normalize for FT-Transformer |",
                "",
                "## A. Scaling",
                "Logistic: `StandardScaler` on continuous columns, train-fit.",
                "XGBoost / CatBoost / foundation TFMs: no external scaling.",
                "TabM / FT-Transformer: train StandardScaler on numerics only.",
                "",
                "## B. Imputation",
                "Logistic / TabM / FTT numerics: train-median. Trees / CatBoost / foundation: leave NaNs.",
                "",
                "## C. Sparse ablation",
                "See `sparse_feature_flags.md` — especially `years_since_last_change`.",
                "",
                "## D. Macros",
                "Low nunique on annual panel; do not collapse. See `macro_grain_audit.json`.",
                "",
                "## V1 / foundation counts",
                f"- logistic/tree V1: **{len(v1_cols)}** cols",
                f"- foundation / catboost-native: **{foundation_info['n_foundation_v1_features']}** cols",
                f"- tabm_v1 / ftt_v1: **{extra['tabm']['n_features']}** cols",
                "",
                "Architecture: `docs/model_architecture.md`. Eval: `eval_protocol.md`.",
                f"Artifacts: `{ARTIFACTS_DIR}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary
