"""Apply approved collapse transforms and macro/missingness audits (modeling layer).

Does not mutate Gold/Silver. Division-by-zero → null. No zero-fill of unavailable values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, QUALITY_DIR, SILVER_DIR
from src.modeling.feature_analysis import (
    PANEL_PATH,
    REPORT_DIR,
    build_inventory,
    build_model_ready_schema_report,
    build_numeric_preview,
    build_numeric_preview_aligned,
    model_ready_readiness_md,
    train_complete_mask,
    _truthy_followup,
)

ENGINEERED_NAME = "train_numeric_engineered.parquet"
MODEL_READY_GOLD_DIR = GOLD_DIR / "modeling"
SPLITS = ("train", "val", "test", "score")


def split_row_mask(df: pd.DataFrame, split: str) -> pd.Series:
    """Train/val/test require complete_followup; score keeps all score rows."""
    m = df["split"].astype(str).eq(split)
    if split == "score":
        return m
    if "complete_followup" in df.columns:
        m = m & _truthy_followup(df["complete_followup"])
    return m


def _assemble_model_ready(X: pd.DataFrame, panel_slice: pd.DataFrame) -> pd.DataFrame:
    engineered = X.copy()
    engineered.insert(0, "project_key", panel_slice["project_key"].to_numpy())
    engineered.insert(1, "observation_date", pd.to_datetime(panel_slice["observation_date"]).to_numpy())
    if "withdraw_next_12m" in panel_slice.columns:
        engineered.insert(
            2,
            "withdraw_next_12m",
            pd.to_numeric(panel_slice["withdraw_next_12m"], errors="coerce").to_numpy(),
        )
    else:
        engineered.insert(2, "withdraw_next_12m", np.nan)
    return engineered


def build_split_matrix(
    panel_slice: pd.DataFrame,
    *,
    feature_cols: list[str],
    matrix_meta: dict[str, Any],
    collapse_change_history: bool,
) -> pd.DataFrame:
    """Apply derives + frozen train schema to one split."""
    derived, notes = apply_panel_derives(panel_slice)
    # Honor train collapse decision for capacity/service flag
    if collapse_change_history and "project_change_history_available" not in derived.columns:
        cap_miss = derived["capacity_change_pct"].isna() if "capacity_change_pct" in derived.columns else None
        svc_miss = (
            derived["service_date_shift_months"].isna()
            if "service_date_shift_months" in derived.columns
            else None
        )
        if cap_miss is not None and svc_miss is not None:
            derived["project_change_history_available"] = ((~cap_miss) | (~svc_miss)).astype("float64")

    X = build_numeric_preview_aligned(derived, feature_cols, matrix_meta)
    # Ensure derived / availability columns present
    for col in feature_cols:
        if col not in X.columns and col in derived.columns:
            X[col] = pd.to_numeric(derived[col], errors="coerce").to_numpy()
    X = X.reindex(columns=feature_cols)
    return _assemble_model_ready(X, derived)


# Columns dropped from the engineered matrix after transforms
DROP_AFTER_DERIVE = [
    "years_in_queue",
    "same_poi_project_count",
    "prior_12m_withdrawn_mw",
    "developer_total_active_mw",
    "other_active_mw_same_state",
    "news_count_30d",
    "negative_news_count_90d",
    "restudy_count_missing",
    "study_delay_days_missing",
    "miso_demand_yoy_pct_missing",
    "miso_generation_yoy_pct_missing",
]

MACRO_COLS = [
    "interest_rate_at_observation",
    "interest_rate_at_entry",
    "interest_rate_change_since_entry",
    "construction_cost_index_change_12m",
    "miso_mean_demand_mw",
    "miso_peak_demand_mw",
    "miso_demand_yoy_pct",
    "miso_generation_yoy_pct",
    "miso_net_interchange_mw",
]


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    n = pd.to_numeric(num, errors="coerce")
    d = pd.to_numeric(den, errors="coerce")
    out = pd.Series(np.nan, index=n.index, dtype="float64")
    ok = d.notna() & n.notna() & (d > 0)
    out.loc[ok] = (n.loc[ok] / d.loc[ok]).astype("float64")
    return out


def _present(s: pd.Series) -> pd.Series:
    return s.notna().astype("float64")


def apply_panel_derives(train: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Add derived columns on the train panel slice (before numeric preview)."""
    out = train.copy()
    notes: dict[str, Any] = {"derived": [], "availability_flags": []}

    # Prior withdrawals: severity
    if "prior_12m_withdrawn_mw" in out.columns and "prior_12m_withdrawal_count" in out.columns:
        out["avg_withdrawn_mw_12m"] = _safe_div(out["prior_12m_withdrawn_mw"], out["prior_12m_withdrawal_count"])
        notes["derived"].append("avg_withdrawn_mw_12m")

    # Developer average size
    if "developer_total_active_mw" in out.columns and "developer_active_project_count" in out.columns:
        out["developer_avg_active_project_mw"] = _safe_div(
            out["developer_total_active_mw"], out["developer_active_project_count"]
        )
        notes["derived"].append("developer_avg_active_project_mw")

    # State average project size
    if "other_active_mw_same_state" in out.columns and "other_active_projects_same_state" in out.columns:
        out["avg_active_project_mw_state"] = _safe_div(
            out["other_active_mw_same_state"], out["other_active_projects_same_state"]
        )
        notes["derived"].append("avg_active_project_mw_state")

    # News: intensity + negative share
    n30 = pd.to_numeric(out.get("news_count_30d"), errors="coerce") if "news_count_30d" in out.columns else None
    n90 = pd.to_numeric(out.get("news_count_90d"), errors="coerce") if "news_count_90d" in out.columns else None
    nneg = (
        pd.to_numeric(out.get("negative_news_count_90d"), errors="coerce")
        if "negative_news_count_90d" in out.columns
        else None
    )
    if n30 is not None and n90 is not None:
        intensity = pd.Series(np.nan, index=out.index, dtype="float64")
        ok = n90.notna() & (n90 > 0) & n30.notna()
        intensity.loc[ok] = (3.0 * n30.loc[ok] / n90.loc[ok]).astype("float64")
        out["news_recent_intensity"] = intensity
        notes["derived"].append("news_recent_intensity")
    if nneg is not None and n90 is not None:
        share = pd.Series(np.nan, index=out.index, dtype="float64")
        ok = n90.notna() & (n90 > 0) & nneg.notna()
        share.loc[ok] = (nneg.loc[ok] / n90.loc[ok]).astype("float64")
        out["negative_news_share_90d"] = share
        notes["derived"].append("negative_news_share_90d")

    # DPP delay info available (collapse identical missingness)
    restudy = out["restudy_count"] if "restudy_count" in out.columns else pd.Series(pd.NA, index=out.index)
    delay = out["study_delay_days"] if "study_delay_days" in out.columns else pd.Series(pd.NA, index=out.index)
    out["dpp_delay_info_available"] = ((restudy.notna()) | (delay.notna())).astype("float64")
    notes["availability_flags"].append("dpp_delay_info_available")

    # EIA YoY available
    dem = out["miso_demand_yoy_pct"] if "miso_demand_yoy_pct" in out.columns else pd.Series(pd.NA, index=out.index)
    gen = (
        out["miso_generation_yoy_pct"]
        if "miso_generation_yoy_pct" in out.columns
        else pd.Series(pd.NA, index=out.index)
    )
    out["eia_yoy_available"] = ((dem.notna()) | (gen.notna())).astype("float64")
    notes["availability_flags"].append("eia_yoy_available")

    # Capacity/service change history — collapse if missing patterns agree ≥ 0.99
    cap_miss = out["capacity_change_pct"].isna() if "capacity_change_pct" in out.columns else None
    svc_miss = out["service_date_shift_months"].isna() if "service_date_shift_months" in out.columns else None
    notes["project_change_history"] = {"collapsed": False, "agreement": None}
    if cap_miss is not None and svc_miss is not None:
        agree = float((cap_miss == svc_miss).mean())
        notes["project_change_history"]["agreement"] = agree
        if agree >= 0.99:
            # available when either value present (same as not both missing)
            out["project_change_history_available"] = (
                (~cap_miss) | (~svc_miss)
            ).astype("float64")
            notes["availability_flags"].append("project_change_history_available")
            notes["project_change_history"]["collapsed"] = True

    return out, notes


def drop_engineered_columns(X: pd.DataFrame, collapse_change_history: bool) -> pd.DataFrame:
    drop = list(DROP_AFTER_DERIVE)
    if collapse_change_history:
        drop.extend(["capacity_change_pct_missing", "service_date_shift_months_missing"])
    present = [c for c in drop if c in X.columns]
    return X.drop(columns=present, errors="ignore"), present


def audit_macro_grain(train: pd.DataFrame) -> dict[str, Any]:
    """Audit macro correlations at panel vs native time grain — do not collapse."""
    audit: dict[str, Any] = {
        "recommendation": "keep_macros_as_is",
        "warning": (
            "Annual Gold repeats a few year-level macro values across thousands of projects; "
            "project-row Pearson correlations are misleading. Prefer native year_month grain."
        ),
        "panel_train_nunique": {},
        "panel_train_corr": None,
        "native_grain": {},
    }

    cols = [c for c in MACRO_COLS if c in train.columns]
    for c in cols:
        audit["panel_train_nunique"][c] = int(pd.to_numeric(train[c], errors="coerce").nunique(dropna=True))

    if len(cols) >= 2:
        corr = train[cols].apply(pd.to_numeric, errors="coerce").corr(method="pearson", min_periods=30)
        audit["panel_train_corr"] = corr.round(4).to_dict()

    # Native grain from market_zone_month
    mz_path = SILVER_DIR / "enrichment" / "market_zone_month.parquet"
    native: dict[str, Any] = {"path": str(mz_path), "exists": mz_path.exists()}
    if mz_path.exists():
        m = pd.read_parquet(mz_path)
        key_cols = [c for c in ["year_month", "miso_zone", "geographic_key"] if c in m.columns]
        feat_map = {
            "interest_rate_10y": "interest_rate_at_observation",
            "ppi_construction": "construction_cost_index_proxy",
            "miso_mean_demand_mw": "miso_mean_demand_mw",
            "miso_peak_demand_mw": "miso_peak_demand_mw",
            "miso_demand_yoy_pct": "miso_demand_yoy_pct",
            "miso_generation_yoy_pct": "miso_generation_yoy_pct",
            "miso_net_interchange_mw": "miso_net_interchange_mw",
        }
        use = [c for c in feat_map if c in m.columns]
        if key_cols and use:
            dedup = m.drop_duplicates(key_cols)[key_cols + use].copy()
            for c in use:
                dedup[c] = pd.to_numeric(dedup[c], errors="coerce")
            # YoY needs lag — compute on sorted year_month if present
            if "year_month" in dedup.columns and "miso_mean_demand_mw" in dedup.columns:
                dedup = dedup.sort_values("year_month")
            native["n_rows_dedup"] = int(len(dedup))
            native["nunique"] = {c: int(dedup[c].nunique(dropna=True)) for c in use}
            if len(use) >= 2:
                native["corr"] = dedup[use].corr(method="pearson", min_periods=12).round(4).to_dict()
            native["year_month_nunique"] = (
                int(dedup["year_month"].nunique()) if "year_month" in dedup.columns else None
            )
        else:
            native["note"] = "missing expected columns for dedup corr"
    audit["native_grain"] = native

    # Observation-year uniqueness on train (what Gold actually has)
    t = train.copy()
    t["_obs_year"] = pd.to_datetime(t["observation_date"]).dt.year
    year_level = (
        t.groupby("_obs_year", as_index=False)[[c for c in cols if c in t.columns]]
        .first()
        .apply(pd.to_numeric, errors="coerce")
        if cols
        else pd.DataFrame()
    )
    audit["train_observation_year_rows"] = int(len(year_level))
    if len(year_level) >= 2 and len(cols) >= 2:
        ycols = [c for c in cols if c in year_level.columns]
        audit["train_year_level_corr"] = (
            year_level[ycols].corr(method="pearson").round(4).to_dict() if len(ycols) >= 2 else None
        )
        audit["train_year_level_nunique"] = {c: int(year_level[c].nunique(dropna=True)) for c in ycols}

    return audit


def audit_study_service_missing(train: pd.DataFrame) -> dict[str, Any]:
    """Keep study_phase_missing and service_type_missing; document relationship."""
    sp = train["study_phase"].isna() if "study_phase" in train.columns else None
    st = train["service_type"].isna() if "service_type" in train.columns else None
    out: dict[str, Any] = {
        "recommendation": "keep_both_pending_audit",
        "reason": "r≈-0.95 suggests complementary missingness, not identical availability — do not merge automatically.",
    }
    if sp is None or st is None:
        out["status"] = "columns_missing"
        return out
    out["study_phase_missing_rate"] = float(sp.mean())
    out["service_type_missing_rate"] = float(st.mean())
    out["agreement_rate"] = float((sp == st).mean())
    out["complement_rate"] = float((sp != st).mean())
    # crosstab counts
    ct = pd.crosstab(sp.rename("study_phase_na"), st.rename("service_type_na"))
    out["crosstab"] = {str(k): {str(k2): int(v) for k2, v in row.items()} for k, row in ct.to_dict().items()}
    # pearson on 0/1
    r = float(np.corrcoef(sp.astype(float), st.astype(float))[0, 1])
    out["pearson_missing_indicators"] = r
    return out


def _engineering_notes_md(manifest: dict[str, Any], macro: dict[str, Any], study_svc: dict[str, Any]) -> str:
    lines = [
        "# Feature engineering notes",
        "",
        "Train-only engineered **model-ready** matrix (collapsed/derived features — not statistical regularization).",
        "Gold/Silver unchanged.",
        "",
        "## Applied transforms",
        "",
    ]
    for item in manifest.get("transforms", []):
        lines.append(f"- **{item['cluster']}**: {item['action']}")
    lines.extend(["", "## Dropped from engineered matrix", ""])
    for c in manifest.get("dropped_columns", []):
        lines.append(f"- `{c}`")
    lines.extend(["", "## Derived columns", ""])
    for c in manifest.get("derived_columns", []):
        lines.append(f"- `{c}`")
    lines.extend(
        [
            "",
            "## Macro audit (not collapsed)",
            "",
            f"- Recommendation: `{macro.get('recommendation')}`",
            f"- Warning: {macro.get('warning')}",
            f"- Panel train nunique: `{json.dumps(macro.get('panel_train_nunique'))}`",
            f"- Train observation-year rows: {macro.get('train_observation_year_rows')}",
            "",
            "## Study/service missingness (kept both)",
            "",
            f"- Recommendation: `{study_svc.get('recommendation')}`",
            f"- Pearson(missing indicators): {study_svc.get('pearson_missing_indicators')}",
            f"- Agreement: {study_svc.get('agreement_rate')}; complement: {study_svc.get('complement_rate')}",
            "",
            f"Model-ready train file: `{manifest.get('model_ready_path')}`",
            f"Engineered parquet (report mirror): `{manifest.get('engineered_path')}`",
            f"Schema / readiness: `model_ready_schema.csv`, `model_ready_readiness.md`",
            "",
        ]
    )
    return "\n".join(lines)


def run_feature_engineering(
    panel_path: Path | None = None,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    panel_path = panel_path or PANEL_PATH
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    MODEL_READY_GOLD_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(panel_path)
    train = df.loc[train_complete_mask(df)].copy()
    train_derived, derive_notes = apply_panel_derives(train)

    inventory = build_inventory(df, train_derived)

    X, matrix_meta = build_numeric_preview(train_derived, inventory)
    collapse_hist = bool(derive_notes.get("project_change_history", {}).get("collapsed"))
    X2, dropped = drop_engineered_columns(X, collapse_change_history=collapse_hist)

    for flag in derive_notes.get("availability_flags", []):
        if flag in train_derived.columns and flag not in X2.columns:
            X2[flag] = pd.to_numeric(train_derived[flag], errors="coerce").to_numpy()

    for dcol in derive_notes.get("derived", []):
        if dcol in train_derived.columns and dcol not in X2.columns:
            X2[dcol] = pd.to_numeric(train_derived[dcol], errors="coerce").to_numpy()

    feature_cols = list(X2.columns)
    matrix_meta = dict(matrix_meta)
    matrix_meta["frozen_feature_columns"] = feature_cols

    macro_audit = audit_macro_grain(train)
    study_svc_audit = audit_study_service_missing(train)

    engineered = _assemble_model_ready(X2, train_derived)
    eng_path = report_dir / ENGINEERED_NAME
    model_ready_paths: dict[str, str] = {}
    engineered.to_parquet(eng_path, index=False)
    train_path = MODEL_READY_GOLD_DIR / "model_ready_train.parquet"
    train_csv = MODEL_READY_GOLD_DIR / "model_ready_train.csv"
    engineered.to_parquet(train_path, index=False)
    engineered.to_csv(train_csv, index=False)
    model_ready_paths["train"] = str(train_path)

    for split in ("val", "test", "score"):
        sl = df.loc[split_row_mask(df, split)].copy()
        if sl.empty:
            continue
        ready = build_split_matrix(
            sl,
            feature_cols=feature_cols,
            matrix_meta=matrix_meta,
            collapse_change_history=collapse_hist,
        )
        outp = MODEL_READY_GOLD_DIR / f"model_ready_{split}.parquet"
        ready.to_parquet(outp, index=False)
        ready.to_csv(MODEL_READY_GOLD_DIR / f"model_ready_{split}.csv", index=False)
        model_ready_paths[split] = str(outp)

    for legacy in (
        MODEL_READY_GOLD_DIR / "train_regularized.parquet",
        MODEL_READY_GOLD_DIR / "train_regularized.csv",
    ):
        if legacy.exists():
            legacy.unlink()

    schema = build_model_ready_schema_report(engineered)
    schema_path = report_dir / "model_ready_schema.csv"
    readiness_path = report_dir / "model_ready_readiness.md"
    schema.to_csv(schema_path, index=False)
    readiness_path.write_text(
        model_ready_readiness_md(schema, str(train_path), len(engineered)),
        encoding="utf-8",
    )

    (MODEL_READY_GOLD_DIR / "frozen_feature_columns.json").write_text(
        json.dumps(
            {"feature_columns": feature_cols, "matrix_meta": matrix_meta},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    transforms = [
        {"cluster": "queue_age", "action": "Keep queue_age_months; drop years_in_queue"},
        {"cluster": "poi_congestion", "action": "Keep other_active_projects_same_poi; drop same_poi_project_count"},
        {
            "cluster": "prior_withdrawals",
            "action": "Keep count; add avg_withdrawn_mw_12m; drop prior_12m_withdrawn_mw",
        },
        {
            "cluster": "developer_scale",
            "action": "Keep developer_active_project_count; add developer_avg_active_project_mw; drop total MW",
        },
        {
            "cluster": "state_pressure",
            "action": "Keep other_active_projects_same_state; add avg_active_project_mw_state; drop other_active_mw_same_state",
        },
        {
            "cluster": "news",
            "action": "Keep news_count_90d; add news_recent_intensity + negative_news_share_90d; drop N30 and Nneg counts",
        },
        {
            "cluster": "dpp_missingness",
            "action": "Collapse to dpp_delay_info_available; keep restudy_count and study_delay_days values",
        },
        {
            "cluster": "eia_yoy_missingness",
            "action": "Collapse to eia_yoy_available; keep YoY values",
        },
        {
            "cluster": "capacity_service_missingness",
            "action": (
                "Collapsed to project_change_history_available"
                if collapse_hist
                else "Kept both missing indicators (agreement < 0.99)"
            ),
        },
        {"cluster": "macro", "action": "NOT collapsed — see macro_grain_audit.json"},
        {"cluster": "study_service_missing", "action": "Kept both — see study_service_missing_audit.json"},
    ]

    manifest = {
        "train_rows": int(len(train_derived)),
        "engineered_shape": [int(engineered.shape[0]), int(engineered.shape[1])],
        "feature_cols": int(len(feature_cols)),
        "derived_columns": derive_notes.get("derived", []),
        "availability_flags": derive_notes.get("availability_flags", []),
        "dropped_columns": dropped,
        "project_change_history": derive_notes.get("project_change_history"),
        "transforms": transforms,
        "matrix_meta": matrix_meta,
        "engineered_path": str(eng_path),
        "model_ready_path": str(train_path),
        "model_ready_csv_path": str(train_csv),
        "model_ready_paths": model_ready_paths,
        "schema_path": str(schema_path),
        "readiness_path": str(readiness_path),
        "all_features_numeric": all(pd.api.types.is_numeric_dtype(X2[c]) for c in X2.columns),
    }

    (report_dir / "feature_engineering_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    (report_dir / "macro_grain_audit.json").write_text(
        json.dumps(macro_audit, indent=2, default=str), encoding="utf-8"
    )
    (report_dir / "study_service_missing_audit.json").write_text(
        json.dumps(study_svc_audit, indent=2, default=str), encoding="utf-8"
    )
    (report_dir / "feature_engineering_notes.md").write_text(
        _engineering_notes_md(manifest, macro_audit, study_svc_audit), encoding="utf-8"
    )
    (MODEL_READY_GOLD_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Model-ready matrices",
                "",
                "`model_ready_{train,val,test,score}.parquet` — numeric feature matrices after",
                "approved collapse / derive transforms (not statistical regularization).",
                "One-hot / drop schema is **frozen from train**.",
                "",
                "Preprocessing (train-only impute/scale for logistic; NaNs for trees):",
                "`logistic_ready_*` / `tree_ready_*` via `scripts/prepare_model_matrices.py`.",
                "",
                "Schema: `data/quality_reports/modeling/model_ready_schema.csv`",
                "Readiness: `data/quality_reports/modeling/model_ready_readiness.md`",
                "",
                "Exclude `project_key` and `observation_date` from `X`. Label: `withdraw_next_12m`.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    summary = {
        "manifest": manifest,
        "macro_audit_panel_nunique": macro_audit.get("panel_train_nunique"),
        "macro_recommendation": macro_audit.get("recommendation"),
        "study_service_recommendation": study_svc_audit.get("recommendation"),
        "schema_role_counts": schema["role"].value_counts().to_dict(),
        "model_ready_paths": model_ready_paths,
        "reports_dir": str(report_dir),
    }
    (report_dir / "feature_engineering_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return summary
