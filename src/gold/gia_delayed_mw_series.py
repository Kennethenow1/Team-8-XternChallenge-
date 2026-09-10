"""PIT quarterly delayed-MW stock from EIA-860M planned-COD shifts.

Primary series: MISO planned / under-construction MW whose planned COD has
slipped ≥12 months vs first seen. GIA overlay uses last GIQ snap ≤ t.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, SILVER_DIR
from src.enrichment.registry import SILVER_ENRICHMENT
from src.gold.cod_delay import is_gia_row

DELAY_MONTHS = 12
OUT_DIR = GOLD_DIR / "delay" / "platinum2"
MONTHLY_PATH = SILVER_ENRICHMENT / "eia_860m_monthly.parquet"
MATCHED_PATH = SILVER_ENRICHMENT / "eia_860m_giq_matched.parquet"
SNAPS_PATH = SILVER_DIR / "snapshots" / "project_snapshots.parquet"


def _expanding_first_cod(keys: pd.Series, cod: pd.Series) -> pd.Series:
    first: dict[str, pd.Timestamp] = {}
    out: list[pd.Timestamp] = []
    for key, val in zip(keys.astype(str), cod, strict=False):
        if key not in first and pd.notna(val):
            first[key] = pd.Timestamp(val)
        out.append(first.get(key, pd.NaT))
    return pd.Series(out, index=keys.index)


def _month_delta(later, earlier) -> float:
    if pd.isna(later) or pd.isna(earlier):
        return float("nan")
    later, earlier = pd.Timestamp(later), pd.Timestamp(earlier)
    return float((later.year - earlier.year) * 12 + (later.month - earlier.month))


def _gia_asof(snaps: pd.DataFrame) -> pd.DataFrame:
    df = snaps.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["is_gia"] = [
        is_gia_row(sp, pg)
        for sp, pg in zip(df.get("study_phase", pd.Series(index=df.index)), df.get("post_gia_status"), strict=False)
    ]
    return df.sort_values(["project_key", "observation_date"])


def _gia_flag_at(gia: pd.DataFrame, project_keys: pd.Series, as_of: pd.Timestamp) -> pd.Series:
    hist = gia[gia["observation_date"] <= as_of]
    if hist.empty:
        return pd.Series(False, index=project_keys.index)
    last = hist.groupby("project_key").tail(1).set_index("project_key")["is_gia"]
    mapped = project_keys.map(last)
    return mapped.where(mapped.notna(), False).astype(bool)


def build_entity_panel(monthly: pd.DataFrame) -> pd.DataFrame:
    df = monthly.copy()
    df["available_date"] = pd.to_datetime(df["available_date"])
    df["planned_cod"] = pd.to_datetime(df["planned_cod"], errors="coerce")
    df["nameplate_mw"] = pd.to_numeric(df["nameplate_mw"], errors="coerce").fillna(0.0)
    df = df.sort_values(["entity_key", "available_date"]).reset_index(drop=True)
    df["first_planned_cod"] = _expanding_first_cod(df["entity_key"], df["planned_cod"])
    df["eia_delay_months"] = [
        _month_delta(a, b) for a, b in zip(df["planned_cod"], df["first_planned_cod"], strict=False)
    ]
    df["is_delayed"] = pd.to_numeric(df["eia_delay_months"], errors="coerce").ge(DELAY_MONTHS).fillna(False)
    shift = pd.to_numeric(df.get("eia_planned_cod_shift_months"), errors="coerce")
    df["shift_positive"] = shift.gt(0).fillna(False)
    return df


def build_monthly_series(
    monthly: pd.DataFrame | None = None,
    matched: pd.DataFrame | None = None,
    snaps: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if monthly is None:
        if not MONTHLY_PATH.exists():
            raise FileNotFoundError(f"missing {MONTHLY_PATH}; run EIA-860M harvest first")
        monthly = pd.read_parquet(MONTHLY_PATH)
    if monthly.empty:
        raise ValueError("eia_860m_monthly is empty; refuse to build a 3-point stub series")
    panel = build_entity_panel(monthly)
    if matched is None and MATCHED_PATH.exists():
        matched = pd.read_parquet(MATCHED_PATH)
    if snaps is None and SNAPS_PATH.exists():
        snaps = pd.read_parquet(SNAPS_PATH)
    gia = _gia_asof(snaps) if snaps is not None and not snaps.empty else None

    match_map = pd.DataFrame()
    if matched is not None and not matched.empty and "project_key" in matched.columns:
        match_map = matched.dropna(subset=["project_key"])[
            ["entity_key", "available_date", "project_key"]
        ].copy()
        match_map["available_date"] = pd.to_datetime(match_map["available_date"])

    rows = []
    for t, part in panel.groupby("available_date"):
        t = pd.Timestamp(t)
        delayed = part["is_delayed"].fillna(False)
        mw = part["nameplate_mw"]
        gia_n = 0
        gia_delayed_mw = 0.0
        if gia is not None and not match_map.empty:
            m = part.merge(
                match_map[match_map["available_date"] == t],
                on=["entity_key", "available_date"],
                how="left",
            )
            is_gia = _gia_flag_at(gia, m["project_key"], t)
            gia_n = int((is_gia & m["project_key"].notna()).sum())
            gia_delayed_mw = float(mw.loc[delayed.to_numpy() & is_gia.to_numpy()].sum()) if len(m) else 0.0
        rows.append(
            {
                "available_date": t,
                "year_month": f"{t.year:04d}-{t.month:02d}",
                "year": int(t.year),
                "month": int(t.month),
                "delayed_mw": float(mw.loc[delayed].sum()),
                "gia_delayed_mw": gia_delayed_mw,
                "shift_in_mw": float(mw.loc[part["shift_positive"]].sum()),
                "n_generators": int(len(part)),
                "n_delayed": int(delayed.sum()),
                "gia_n": gia_n,
                "planned_mw": float(mw.sum()),
            }
        )
    out = pd.DataFrame(rows).sort_values("available_date").reset_index(drop=True)
    n = len(out)
    origin_split = []
    for ym in out["year_month"].astype(str):
        y = int(ym[:4])
        if y <= 2022:
            origin_split.append("train")
        elif y == 2023:
            origin_split.append("val")
        elif y == 2024:
            origin_split.append("test")
        else:
            origin_split.append("score")
    out["origin_split"] = origin_split
    out["n_snapshots"] = n
    return out


def series_audit(series: pd.DataFrame) -> dict[str, Any]:
    delayed = pd.to_numeric(series["delayed_mw"], errors="coerce")
    gia = pd.to_numeric(series["gia_delayed_mw"], errors="coerce")
    share = float((gia / delayed.replace(0, np.nan)).median()) if delayed.gt(0).any() else 0.0
    return {
        "n_snapshots": int(len(series)),
        "year_months": series["year_month"].astype(str).tolist(),
        "delayed_mw_min": float(delayed.min()) if len(delayed) else None,
        "delayed_mw_max": float(delayed.max()) if len(delayed) else None,
        "delayed_mw_zeros": int(delayed.eq(0).sum()),
        "gia_delayed_mw_zeros": int(gia.eq(0).sum()) if len(gia) else None,
        "gia_match_mw_share_median": share,
        "enough_for_timesfm": int(len(series)) >= 12,
        "note": (
            "Primary target is delayed_mw (EIA planned stock). "
            "gia_delayed_mw is a thin matched overlay; forecast delayed_mw if GIA is sparse."
        ),
    }


def split_manifest(series: pd.DataFrame) -> dict[str, Any]:
    return {
        "task": "gia_delayed_mw_next_year",
        "primary_target": "delayed_mw",
        "overlay": "gia_delayed_mw",
        "grain": "EIA-860M quarterly (Mar/Jun/Sep/Dec)",
        "horizons_months": [3, 12],
        "horizon_steps": {"3": 1, "12": 4},
        "val_3m": "origins in 2023 whose target year <= 2023",
        "val_12m": "origins whose target year <= 2023 (typically 2022-q → 2023-q)",
        "test_sealed": 2024,
        "n_snapshots": int(len(series)),
        "counts_by_origin_split": series["origin_split"].value_counts().to_dict(),
        "year_months": series["year_month"].astype(str).tolist(),
    }


def write_gold(series: pd.DataFrame, audit: dict[str, Any], manifest: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    series.to_parquet(OUT_DIR / "gia_delayed_mw_monthly.parquet", index=False)
    series.to_csv(OUT_DIR / "gia_delayed_mw_monthly.csv", index=False)
    (OUT_DIR / "series_audit.json").write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "split_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    readme = OUT_DIR / "README.md"
    readme.write_text(
        """# Platinum 2 gold — delayed MW sitting in GIA

This is **not** “how many months will this one project slip.”

Each quarter we look at EIA-860M planned generators in MISO states and add up
megawatts whose **planned in-service date has already moved out by a year or
more** compared with the first time we saw that generator.

- `delayed_mw` is the series we can actually forecast (dense EIA quarters).
- `gia_delayed_mw` is the same stock, but only generators we can match to a
  GIQ project that was already in GIA / IA as of that quarter. The match is
  fuzzy, so this overlay can be thin. If it is too thin, we still forecast
  `delayed_mw` and report GIA as a slice.

GIQ snapshots are year-end. Between Decembers we **carry forward** the last
GIA flag. We never use a later queue snapshot as a feature.

2024 is sealed for picking a model. A 12-month-ahead guess made in late 2023
lands in 2024 — that fold is test, not validation.
""",
        encoding="utf-8",
    )


def build_platinum2_gold() -> dict[str, Any]:
    series = build_monthly_series()
    audit = series_audit(series)
    manifest = split_manifest(series)
    write_gold(series, audit, manifest)
    return {"series": series, "audit": audit, "manifest": manifest}
