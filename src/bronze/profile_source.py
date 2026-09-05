"""Independent source profiling and data-quality reports (no joins)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.bronze.ingest import load_registry_parquet
from src.common.paths import BRONZE_DIR, QUALITY_DIR, ensure_layer_dirs


def _read_raw(source: pd.Series) -> pd.DataFrame:
    path = BRONZE_DIR / source["bronze_subdir"] / source["source_file"]
    mode = source["sheet_mode"]
    if mode == "miso_csv":
        return pd.read_csv(path)
    if mode == "berkeley_2020_split":
        frames = []
        for sheet in ("active", "withdrawn", "completed"):
            d = pd.read_excel(path, sheet_name=sheet)
            d["_sheet"] = sheet
            frames.append(d)
        return pd.concat(frames, ignore_index=True, sort=False)
    if mode == "berkeley_data":
        return pd.read_excel(path, sheet_name="data")
    if mode == "berkeley_lbnl_complete":
        return pd.read_excel(path, sheet_name="03. Complete Queue Data", header=1)
    raise ValueError(f"Unknown sheet_mode: {mode}")


def _id_col(df: pd.DataFrame, source: pd.Series) -> str | None:
    col = source.get("project_id_col")
    if col and col in df.columns:
        return col
    for c in ("q_id", "Project #", "project_id"):
        if c in df.columns:
            return c
    return None


def _status_col(df: pd.DataFrame) -> str | None:
    for c in ("q_status", "Request Status", "status"):
        if c in df.columns:
            return c
    return None


def profile_dataframe(df: pd.DataFrame, source_id: str, id_col: str | None) -> tuple[dict, pd.DataFrame]:
    n = len(df)
    summary = {
        "source_id": source_id,
        "total_rows": n,
        "n_columns": df.shape[1],
    }
    if id_col and id_col in df.columns:
        ids = df[id_col].astype(str)
        summary["unique_project_ids"] = int(ids.nunique(dropna=True))
        summary["exact_duplicate_rows"] = int(df.duplicated().sum())
        summary["duplicate_project_id_rows"] = int(ids.duplicated().sum())
    else:
        summary["unique_project_ids"] = None
        summary["exact_duplicate_rows"] = int(df.duplicated().sum())
        summary["duplicate_project_id_rows"] = None

    status_col = _status_col(df)
    if status_col:
        summary["status_counts"] = df[status_col].astype(str).value_counts(dropna=False).to_dict()

    field_rows = []
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        # Also count empty strings
        if s.dtype == object:
            missing += int((s.astype(str).str.strip() == "").sum())
        distinct = int(s.nunique(dropna=True))
        invalid = 0
        vmin = vmax = None
        if pd.api.types.is_numeric_dtype(s):
            vmin = s.min()
            vmax = s.max()
            invalid = int((~pd.to_numeric(s, errors="coerce").notna() & s.notna()).sum()) if False else 0
        else:
            # Only attempt datetime/numeric coercion on date-like or numeric-like names
            col_l = str(col).lower()
            looks_date = any(k in col_l for k in ("date", "year", "_on", "time"))
            looks_num = any(k in col_l for k in ("mw", "cap", "fips", "lat", "lon", "days"))
            if looks_date:
                sample = s.dropna().head(200)
                coerced = pd.to_datetime(sample, errors="coerce")
                if len(sample) and coerced.notna().mean() > 0.5:
                    full = pd.to_datetime(s, errors="coerce")
                    vmin = str(full.min()) if full.notna().any() else None
                    vmax = str(full.max()) if full.notna().any() else None
                    invalid = int(s.notna().sum() - full.notna().sum())
            elif looks_num:
                num = pd.to_numeric(s, errors="coerce")
                if num.notna().sum() > max(3, 0.5 * s.notna().sum()):
                    vmin = num.min()
                    vmax = num.max()
        field_rows.append(
            {
                "source": source_id,
                "field": col,
                "missing_count": missing,
                "missing_pct": round(100.0 * missing / n, 3) if n else None,
                "distinct_values": distinct,
                "invalid_count": invalid,
                "minimum": vmin,
                "maximum": vmax,
            }
        )
    return summary, pd.DataFrame(field_rows)


def apply_region_filter(df: pd.DataFrame, source: pd.Series) -> pd.DataFrame:
    col = source.get("region_filter_col")
    val = source.get("region_filter_value")
    if col and val and col in df.columns:
        return df[df[col].astype(str).str.upper() == str(val).upper()].copy()
    return df


def profile_all(require_pass: bool = True) -> pd.DataFrame:
    ensure_layer_dirs()
    registry = load_registry_parquet()
    all_fields = []
    summaries = []
    gate_failures = []

    for _, source in registry.iterrows():
        df = _read_raw(source)
        id_col = _id_col(df, source)
        summary, fields = profile_dataframe(df, source["source_id"], id_col)

        # MISO-filtered view for Berkeley
        filtered = apply_region_filter(df, source)
        summary["rows_after_region_filter"] = len(filtered)
        if source["source_name"] == "Berkeley":
            if len(filtered) == 0:
                gate_failures.append(f"{source['source_id']}: MISO filter returned 0 rows")
            summary["miso_unique_ids"] = (
                int(filtered[id_col].astype(str).nunique()) if id_col and len(filtered) else 0
            )

        # Basic gates
        if summary["total_rows"] == 0:
            gate_failures.append(f"{source['source_id']}: zero rows")
        if id_col is None:
            gate_failures.append(f"{source['source_id']}: missing project id column")
        elif summary.get("unique_project_ids", 0) == 0:
            gate_failures.append(f"{source['source_id']}: no unique project ids")

        status_col = _status_col(df)
        if status_col is None:
            gate_failures.append(f"{source['source_id']}: missing status column")

        # Capacity distribution / tech categories for report sidecar
        cap_cols = [c for c in df.columns if str(c).lower() in {"mw1", "mw_1", "summer mw", "winter mw"}]
        if cap_cols:
            caps = pd.to_numeric(df[cap_cols[0]], errors="coerce")
            summary["capacity_min"] = float(caps.min()) if caps.notna().any() else None
            summary["capacity_max"] = float(caps.max()) if caps.notna().any() else None
            summary["capacity_median"] = float(caps.median()) if caps.notna().any() else None

        tech_cols = [c for c in df.columns if str(c).lower() in {"type_clean", "fuel", "type1", "type_1"}]
        if tech_cols:
            summary["technology_categories"] = (
                df[tech_cols[0]].astype(str).value_counts().head(20).to_dict()
            )

        summaries.append(summary)
        all_fields.append(fields)

        # Write per-source field report
        out = QUALITY_DIR / f"{source['source_id']}_field_profile.csv"
        fields.to_csv(out, index=False)

    field_all = pd.concat(all_fields, ignore_index=True)
    field_all.to_csv(QUALITY_DIR / "field_profile_all.csv", index=False)
    summary_df = pd.DataFrame(summaries)
    summary_df.to_json(QUALITY_DIR / "source_summaries.json", orient="records", indent=2)
    summary_df.to_csv(QUALITY_DIR / "source_summaries.csv", index=False)

    gate_path = QUALITY_DIR / "profile_gate.txt"
    if gate_failures:
        gate_path.write_text("FAIL\n" + "\n".join(gate_failures) + "\n", encoding="utf-8")
        if require_pass:
            raise RuntimeError("Profile gate failed:\n" + "\n".join(gate_failures))
    else:
        gate_path.write_text("PASS\n", encoding="utf-8")

    return summary_df


if __name__ == "__main__":
    print(profile_all(require_pass=True))
