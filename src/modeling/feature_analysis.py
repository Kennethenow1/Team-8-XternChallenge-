"""Train-only feature analysis: inventory, numeric preview, redundancy, label links.

Does not mutate Gold/Silver. Does not fit models on val/test/score.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, QUALITY_DIR

PANEL_PATH = GOLD_DIR / "withdrawal_panel_enriched.parquet"
REPORT_DIR = QUALITY_DIR / "modeling"

LABEL_COLS = {
    "withdraw_next_12m",
    "next_outcome",
    "complete_followup",
    "withdrawal_event",
    "operation_event",
    "outcome_type",
    "outcome_date",
}

ID_COLS = {
    "project_key",
    "poi_key",
    "developer_id",
    "county_fips",
    "source_id",
    "source_name",
}

META_COLS = {
    "split",
    "never_in_training",
    "observation_date",
    "published_at",
    "queue_date",
    "pep_vintage",
    "latest_study_phase",
}

ONEHOT_CATS = (
    "technology_primary",
    "state_code",
    "study_phase",
    "service_type",
    "miso_zone",
    "study_group",
)

FAMILY_PATTERNS: dict[str, tuple[str, ...]] = {
    "queue": (
        "queue_age_months",
        "log1p_capacity_mw",
        "capacity_mw",
        "is_hybrid",
        "months_until_service",
        "service_date_passed",
        "capacity_change_pct",
        "service_date_shift_months",
        "years_since_last_change",
        "other_active_projects_same_state",
        "other_active_mw_same_state",
        "other_active_projects_same_poi",
        "other_active_mw_same_poi",
        "other_active_mw_same_technology",
        "prior_12m_withdrawal_count",
        "prior_12m_withdrawn_mw",
        "years_in_queue",
        "same_poi_project_count",
        "nearby_queue_mw",
        "same_group_prior_withdrawal_rate",
        "developer_active_project_count",
        "developer_total_active_mw",
        "developer_prior_completion_rate",
        "developer_prior_withdrawal_rate",
        "technology_primary",
        "state_code",
        "study_phase",
        "service_type",
    ),
    "cost_study": (
        "network_upgrade_cost",
        "study_delay_days",
        "restudy_count",
        "capacity_reduction_pct",
        "upgrade_cost_per_mw",
        "cost_change_since_previous_study",
        "dpp_event_count_to_date",
        "upgrade_cost_change_pct",
    ),
    "grid": (
        "distance_to_transmission_km",
        "nearby_transmission_voltage",
        "nearby_mtep_upgrade_count",
        "mtep_investment_nearby_usd",
        "local_congestion_mean_12m",
        "local_congestion_volatility_12m",
    ),
    "news": (
        "news_count_30d",
        "news_count_90d",
        "news_sentiment_mean_90d",
        "negative_news_count_90d",
        "opposition_event_count_180d",
        "permit_positive_count_180d",
        "financing_positive_count_180d",
        "days_since_last_positive_event",
        "days_since_last_negative_event",
    ),
    "macro": (
        "interest_rate_at_entry",
        "interest_rate_at_observation",
        "interest_rate_change_since_entry",
        "construction_cost_index_change_12m",
        "miso_mean_demand_mw",
        "miso_peak_demand_mw",
        "miso_demand_yoy_pct",
        "miso_generation_yoy_pct",
        "miso_net_interchange_mw",
    ),
    "geo_policy": (
        "population",
        "population_yoy_pct",
        "population_change_since_2020",
        "fema_risk_score",
        "energy_community_eligible",
        "rural_flag",
        "storm_events_12m",
        "storm_property_damage_12m",
        "extreme_weather_days_12m",
        "drought_months_12m",
        "county_gdp_growth",
        "construction_employment_growth",
        "solar_resource_percentile",
        "wind_resource_percentile",
        "wetlands_overlap_pct",
        "distance_to_wetlands_km",
        "expected_incremental_load_mw",
        "developer_financing_event_180d",
        "developer_distress_event_180d",
        "miso_zone",
    ),
}

CORR_THRESHOLD = 0.90
RARE_BUCKET_MIN = 30
MISSING_INDICATOR_MAX_COVERAGE = 0.95


def _truthy_followup(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    if pd.api.types.is_numeric_dtype(s):
        return s.fillna(0).astype(int).eq(1)
    return s.astype(str).str.lower().isin({"true", "1", "1.0", "yes"})


def train_complete_mask(df: pd.DataFrame) -> pd.Series:
    m = df["split"].astype(str).eq("train")
    if "complete_followup" in df.columns:
        m = m & _truthy_followup(df["complete_followup"])
    return m


def classify_column(col: str, series: pd.Series) -> str:
    if col in LABEL_COLS:
        return "label"
    if col in ID_COLS:
        return "id"
    if col in META_COLS:
        return "meta"
    if col.endswith("_status"):
        return "status"
    if col in ONEHOT_CATS:
        return "categorical"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "exclude"
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return "numeric"
    nuniq = series.nunique(dropna=True)
    if nuniq > 50:
        return "exclude"
    if nuniq <= 40:
        return "categorical"
    return "exclude"


def family_for_column(col: str) -> str | None:
    base = col
    if "__" in col:
        base = col.split("__", 1)[0]
    if base.endswith("_missing"):
        base = base[: -len("_missing")]
    for fam, members in FAMILY_PATTERNS.items():
        if base in members or col in members:
            return fam
    return None


def build_inventory(df: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        st = train[col] if col in train.columns else pd.Series(dtype=object)
        role = classify_column(col, s)
        cov_all = float(s.notna().mean()) if len(s) else 0.0
        cov_train = float(st.notna().mean()) if len(st) else 0.0
        rows.append(
            {
                "column": col,
                "dtype": str(s.dtype),
                "role": role,
                "family": family_for_column(col),
                "coverage_all": cov_all,
                "coverage_train": cov_train,
                "nunique_all": int(s.nunique(dropna=True)),
                "nunique_train": int(st.nunique(dropna=True)) if len(st) else 0,
                "all_null": bool(s.isna().all()),
                "constant_train": bool(len(st) and st.nunique(dropna=True) <= 1),
            }
        )
    return pd.DataFrame(rows).sort_values(["role", "family", "column"]).reset_index(drop=True)


def _to_numeric_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype("float64")
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    return pd.to_numeric(s, errors="coerce")


def build_numeric_preview(train: pd.DataFrame, inventory: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """All-numeric train matrix: numerics + one-hots + missing indicators. No zero-fill of values."""
    meta: dict[str, Any] = {
        "onehot_columns": [],
        "numeric_columns": [],
        "missing_indicators": [],
        "skipped": [],
    }
    parts: list[pd.DataFrame] = []
    inv = inventory.set_index("column")

    for col, row in inv.iterrows():
        if row["role"] != "numeric":
            continue
        if row["all_null"] or row["constant_train"]:
            meta["skipped"].append({"column": col, "reason": "all_null_or_constant_train"})
            continue
        s = _to_numeric_series(train[col])
        if s.notna().sum() == 0:
            meta["skipped"].append({"column": col, "reason": "no_numeric_train_values"})
            continue
        frame = pd.DataFrame({col: s})
        cov = float(s.notna().mean())
        if cov < MISSING_INDICATOR_MAX_COVERAGE:
            ind = f"{col}_missing"
            frame[ind] = s.isna().astype("float64")
            meta["missing_indicators"].append(ind)
        parts.append(frame)
        meta["numeric_columns"].append(col)

    for col in ONEHOT_CATS:
        if col not in train.columns:
            continue
        s = train[col].astype(str).where(train[col].notna(), other=np.nan)
        vc = s.value_counts(dropna=True)
        keep = set(vc[vc >= RARE_BUCKET_MIN].index.astype(str))
        levels = sorted(keep)
        if not levels:
            meta["skipped"].append({"column": col, "reason": "no_frequent_levels"})
            continue
        dummies = pd.DataFrame(index=train.index)
        for lev in levels:
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(lev))[:40]
            name = f"{col}__{safe}"
            dummies[name] = (s.astype(str) == str(lev)).astype("float64")
            meta["onehot_columns"].append(name)
        rare_mask = s.notna() & ~s.astype(str).isin(keep)
        if rare_mask.any():
            name = f"{col}__OTHER_RARE"
            dummies[name] = rare_mask.astype("float64")
            meta["onehot_columns"].append(name)
        miss_name = f"{col}_missing"
        dummies[miss_name] = s.isna().astype("float64")
        meta["missing_indicators"].append(miss_name)
        parts.append(dummies)

    if not parts:
        return pd.DataFrame(index=train.index), meta

    out = pd.concat(parts, axis=1)
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    meta["n_rows"] = int(len(out))
    meta["n_cols"] = int(out.shape[1])
    return out, meta


def _corr_pairs(X: pd.DataFrame, cols: list[str], family: str) -> list[dict[str, Any]]:
    use = [c for c in cols if c in X.columns]
    if len(use) < 2:
        return []
    corr = X[use].corr(method="pearson", min_periods=30)
    pairs = []
    for i, a in enumerate(use):
        for b in use[i + 1 :]:
            r = corr.loc[a, b]
            if pd.isna(r):
                continue
            if abs(float(r)) >= CORR_THRESHOLD:
                pairs.append(
                    {
                        "family": family,
                        "feature_a": a,
                        "feature_b": b,
                        "pearson_r": float(r),
                        "abs_r": abs(float(r)),
                    }
                )
    return pairs


def high_correlation_pairs(X: pd.DataFrame) -> pd.DataFrame:
    by_fam: dict[str, list[str]] = defaultdict(list)
    for c in X.columns:
        fam = family_for_column(c) or "other"
        by_fam[fam].append(c)

    rows: list[dict[str, Any]] = []
    for fam, cols in by_fam.items():
        rows.extend(_corr_pairs(X, cols, fam))
    if not rows:
        return pd.DataFrame(columns=["family", "feature_a", "feature_b", "pearson_r", "abs_r"])
    return pd.DataFrame(rows).sort_values(["abs_r", "family"], ascending=[False, True]).reset_index(drop=True)


def connected_clusters(pairs: pd.DataFrame) -> dict[str, list[list[str]]]:
    """Union-find clusters of highly correlated features (hierarchical summary proxy)."""
    by_fam: dict[str, list[list[str]]] = {}
    if pairs.empty:
        return by_fam

    for fam, g in pairs.groupby("family"):
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for _, r in g.iterrows():
            union(str(r["feature_a"]), str(r["feature_b"]))

        buckets: dict[str, list[str]] = defaultdict(list)
        nodes = set(g["feature_a"].astype(str)) | set(g["feature_b"].astype(str))
        for n in nodes:
            buckets[find(n)].append(n)
        clusters = [sorted(v) for v in buckets.values() if len(v) >= 2]
        clusters.sort(key=len, reverse=True)
        by_fam[str(fam)] = clusters
    return by_fam


def label_association(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    y_num = pd.to_numeric(y, errors="coerce")
    rows = []
    for c in X.columns:
        x = pd.to_numeric(X[c], errors="coerce")
        mask = x.notna() & y_num.notna()
        if int(mask.sum()) < 50:
            continue
        if x[mask].nunique() <= 1:
            continue
        r = float(np.corrcoef(x[mask].to_numpy(dtype=float), y_num[mask].to_numpy(dtype=float))[0, 1])
        if np.isnan(r):
            continue
        rows.append(
            {
                "feature": c,
                "family": family_for_column(c),
                "pearson_with_withdraw_next_12m": r,
                "abs_assoc": abs(r),
                "n_complete": int(mask.sum()),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["feature", "family", "pearson_with_withdraw_next_12m", "abs_assoc", "n_complete"]
        )
    return pd.DataFrame(rows).sort_values("abs_assoc", ascending=False).reset_index(drop=True)


def collapse_recommendations_md(
    pairs: pd.DataFrame,
    clusters: dict[str, list[list[str]]],
    inventory: pd.DataFrame,
    label_assoc: pd.DataFrame,
) -> str:
    lines = [
        "# Feature collapse recommendations",
        "",
        "Generated by train-only feature analysis. Suggestions are **not** automatic drops —",
        "review before changing the modeling matrix. Gold/Silver were not modified.",
        "",
        f"Correlation threshold: `|r| >= {CORR_THRESHOLD}` within feature family.",
        "",
        "## High-correlation pairs",
        "",
    ]
    if pairs.empty:
        lines.append("_No within-family pairs at threshold._")
    else:
        lines.append("| Family | Feature A | Feature B | r |")
        lines.append("|--------|-----------|-----------|---|")
        for _, r in pairs.head(40).iterrows():
            lines.append(
                f"| {r['family']} | `{r['feature_a']}` | `{r['feature_b']}` | {r['pearson_r']:.3f} |"
            )

    lines.extend(["", "## Suggested clusters (keep one representative)", ""])
    if not clusters:
        lines.append("_No multi-feature clusters._")
    else:
        for fam, clist in clusters.items():
            lines.append(f"### {fam}")
            for i, cl in enumerate(clist, 1):
                score: dict[str, float] = {}
                if not label_assoc.empty:
                    sub = label_assoc.set_index("feature")
                    for f in cl:
                        if f in sub.index:
                            score[f] = float(sub.loc[f, "abs_assoc"])
                keep = max(score, key=score.get) if score else cl[0]
                drop = [f for f in cl if f != keep]
                lines.append(
                    f"{i}. **Keep** `{keep}`; consider dropping/merging: "
                    + ", ".join(f"`{d}`" for d in drop)
                )
            lines.append("")

    stubs = inventory[inventory["all_null"] | (inventory["coverage_train"] < 0.01)]
    stubs = stubs[stubs["role"].isin(["numeric", "categorical"])]
    lines.extend(["## Near-empty / stub features (do not zero-fill)", ""])
    if stubs.empty:
        lines.append("_None flagged._")
    else:
        for _, r in stubs.iterrows():
            lines.append(
                f"- `{r['column']}` (train coverage={r['coverage_train']:.3f}, role={r['role']})"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- One-hot categoricals are not ordinal codes (no false order).",
            "- Missingness indicators mark unavailable values; do not treat null as zero risk.",
            "- Label associations are exploratory only — use ablation for final selection.",
            "",
        ]
    )
    return "\n".join(lines)


def family_summary(
    inventory: pd.DataFrame,
    pairs: pd.DataFrame,
    clusters: dict[str, list[list[str]]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fam in FAMILY_PATTERNS:
        cols = inventory[
            (inventory["family"] == fam) & (inventory["role"].isin(["numeric", "categorical"]))
        ]
        out[fam] = {
            "n_columns": int(len(cols)),
            "mean_train_coverage": float(cols["coverage_train"].mean()) if len(cols) else 0.0,
            "n_high_corr_pairs": int((pairs["family"] == fam).sum()) if len(pairs) else 0,
            "n_clusters": len(clusters.get(fam, [])),
            "columns": cols["column"].tolist(),
        }
    return out


def run_feature_analysis(
    panel_path: Path | None = None,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    panel_path = panel_path or PANEL_PATH
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(panel_path)
    mask = train_complete_mask(df)
    train = df.loc[mask].copy()
    if "withdraw_next_12m" not in train.columns:
        raise RuntimeError("Panel missing withdraw_next_12m")

    inventory = build_inventory(df, train)
    X, matrix_meta = build_numeric_preview(train, inventory)
    pairs = high_correlation_pairs(X)
    clusters = connected_clusters(pairs)
    y = train["withdraw_next_12m"]
    label_assoc = label_association(X, y)
    fam_sum = family_summary(inventory, pairs, clusters)
    md = collapse_recommendations_md(pairs, clusters, inventory, label_assoc)

    inventory.to_csv(report_dir / "feature_inventory.csv", index=False)
    pairs.to_csv(report_dir / "correlation_pairs_high.csv", index=False)
    label_assoc.to_csv(report_dir / "label_association_train.csv", index=False)
    (report_dir / "feature_family_summary.json").write_text(
        json.dumps(fam_sum, indent=2), encoding="utf-8"
    )
    (report_dir / "collapse_recommendations.md").write_text(md, encoding="utf-8")

    preview = X.copy()
    preview.insert(0, "project_key", train["project_key"].to_numpy())
    preview.insert(1, "observation_date", pd.to_datetime(train["observation_date"]).to_numpy())
    preview.insert(2, "withdraw_next_12m", pd.to_numeric(y, errors="coerce").to_numpy())
    preview.to_parquet(report_dir / "train_numeric_preview.parquet", index=False)

    feat_cols = list(X.columns)
    non_num = [c for c in feat_cols if not pd.api.types.is_numeric_dtype(X[c])]

    summary = {
        "panel_path": str(panel_path),
        "panel_rows": int(len(df)),
        "panel_cols": int(df.shape[1]),
        "train_complete_rows": int(len(train)),
        "numeric_preview_shape": [int(X.shape[0]), int(X.shape[1])],
        "n_inventory_rows": int(len(inventory)),
        "n_high_corr_pairs": int(len(pairs)),
        "n_clusters_by_family": {k: len(v) for k, v in clusters.items()},
        "top_label_associations": label_assoc.head(15).to_dict(orient="records"),
        "matrix_meta": {
            "n_numeric": len(matrix_meta.get("numeric_columns", [])),
            "n_onehot": len(matrix_meta.get("onehot_columns", [])),
            "n_missing_indicators": len(matrix_meta.get("missing_indicators", [])),
            "n_skipped": len(matrix_meta.get("skipped", [])),
        },
        "all_preview_features_numeric": len(non_num) == 0,
        "non_numeric_preview_cols": non_num,
        "reports_dir": str(report_dir),
        "corr_threshold": CORR_THRESHOLD,
    }
    (report_dir / "feature_analysis_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return summary
