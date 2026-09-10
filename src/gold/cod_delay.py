"""Point-in-time COD-slip labels from GIQ snapshots (+ optional EIA-860M).

MISO ``operational_date`` is Appl In Service Date, not proven COD.
``proposed_service_date`` is negotiated ISD. Labels use last-known COD as of t
and the last COD observed in a follow-up window. Berkeley 2024 vintages have
empty service dates, so the default window is 24 months (next usable COD).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, SILVER_DIR

FOLLOWUP_MONTHS = 24
GIA_PHASES = frozenset({"GIA", "IA Executed", "IA Pending", "Operational"})
ADVANCED_POST_GIA = frozenset(
    {"Under Construction", "In Service", "In Service (with Provisional GIA)", "Not Started"}
)
NEURAL_NET_MIN_VAL_LABELED = 200

DELAY_OUTCOME_COLUMNS = (
    "cod_slip_months_next_12m",
    "cod_slip_ge_12m",
    "event_type",
    "complete_followup",
    "delay_from_original_months",
    "future_cod",
    "cod_at_t",
    "cod_at_entry",
)


def month_delta(later, earlier) -> float:
    if pd.isna(later) or pd.isna(earlier):
        return float("nan")
    later, earlier = pd.Timestamp(later), pd.Timestamp(earlier)
    return float((later.year - earlier.year) * 12 + (later.month - earlier.month))


def _cod_from_row(proposed, operational) -> pd.Timestamp:
    if pd.notna(proposed):
        return pd.Timestamp(proposed)
    if pd.notna(operational):
        return pd.Timestamp(operational)
    return pd.NaT


def snapshot_cod_series(snaps: pd.DataFrame) -> pd.Series:
    proposed = pd.to_datetime(snaps.get("proposed_service_date"), errors="coerce")
    operational = pd.to_datetime(snaps.get("operational_date"), errors="coerce")
    return proposed.fillna(operational)


def last_known_cod_table(snaps: pd.DataFrame) -> pd.DataFrame:
    """One row per project_key × observation_date with last non-null COD ≤ that date."""
    df = snaps.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["snap_cod"] = snapshot_cod_series(df)
    df = df.sort_values(["project_key", "observation_date"]).reset_index(drop=True)
    df["last_known_cod"] = df.groupby("project_key")["snap_cod"].ffill()
    first = df.groupby("project_key")["last_known_cod"].transform("first")
    df["cod_at_entry"] = first
    return df[["project_key", "observation_date", "source_name", "snap_cod", "last_known_cod", "cod_at_entry"]]


def attach_future_cod(
    annual: pd.DataFrame,
    snaps: pd.DataFrame,
    *,
    followup_months: int = FOLLOWUP_MONTHS,
    eia: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Vectorized future COD in (t, t+followup] from later snapshots (skip null COD)."""
    out = annual.copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out["horizon_date"] = out["observation_date"] + pd.DateOffset(months=int(followup_months))

    later = snaps.copy()
    later["observation_date"] = pd.to_datetime(later["observation_date"])
    later["snap_cod"] = snapshot_cod_series(later)
    later = later.loc[later["snap_cod"].notna(), ["project_key", "observation_date", "snap_cod"]]
    later = later.rename(columns={"observation_date": "future_obs", "snap_cod": "future_cod"})

    keys = out[["project_key", "observation_date", "horizon_date"]].reset_index(drop=True)
    keys["_row"] = np.arange(len(keys))
    merged = keys.merge(later, on="project_key", how="left")
    in_win = (
        merged["future_obs"].notna()
        & (merged["future_obs"] > merged["observation_date"])
        & (merged["future_obs"] <= merged["horizon_date"])
    )
    win = merged.loc[in_win].sort_values(["_row", "future_obs"])
    last = win.groupby("_row", sort=False).tail(1)
    out["future_cod"] = pd.NaT
    out["future_cod_obs"] = pd.NaT
    if len(last):
        out.loc[last["_row"].to_numpy(), "future_cod"] = last["future_cod"].to_numpy()
        out.loc[last["_row"].to_numpy(), "future_cod_obs"] = last["future_obs"].to_numpy()

    if eia is not None and len(eia) and "project_key" in eia.columns:
        out = _overlay_eia_future_cod(out, eia, followup_months=followup_months)
    return out


def _overlay_eia_future_cod(panel: pd.DataFrame, eia: pd.DataFrame, *, followup_months: int) -> pd.DataFrame:
    e = eia.copy()
    e["available_date"] = pd.to_datetime(e["available_date"], errors="coerce")
    e["planned_cod"] = pd.to_datetime(e.get("planned_cod"), errors="coerce")
    e = e.dropna(subset=["project_key", "available_date", "planned_cod"])
    if e.empty:
        return panel
    left = panel[["project_key", "observation_date", "horizon_date"]].reset_index(drop=True)
    left["_row"] = np.arange(len(left))
    m = left.merge(e, on="project_key", how="left")
    in_win = (
        m["available_date"].notna()
        & (m["available_date"] > m["observation_date"])
        & (m["available_date"] <= m["horizon_date"])
    )
    win = m.loc[in_win].sort_values(["_row", "available_date"])
    last = win.groupby("_row", sort=False).tail(1)
    if last.empty:
        return panel
    panel = panel.copy()
    cur = pd.to_datetime(panel["future_cod"], errors="coerce")
    upd = pd.Series(pd.NaT, index=panel.index)
    upd.iloc[last["_row"].to_numpy()] = pd.to_datetime(last["planned_cod"]).to_numpy()
    use_eia = cur.isna() & upd.notna()
    panel["future_cod"] = cur.where(~use_eia, upd)
    panel["eia_future_cod_used"] = use_eia.fillna(False).astype(int)
    return panel


def _withdrawn_in_window(panel: pd.DataFrame, outcomes: pd.DataFrame, *, followup_months: int) -> pd.Series:
    wd = outcomes[["project_key", "outcome_type", "outcome_date"]].copy() if len(outcomes) else pd.DataFrame()
    if wd.empty:
        return pd.Series(False, index=panel.index)
    wd["outcome_date"] = pd.to_datetime(wd["outcome_date"], errors="coerce")
    wd = wd[wd["outcome_type"].astype(str).eq("withdrawn") & wd["outcome_date"].notna()]
    m = panel[["project_key", "observation_date"]].reset_index(drop=True)
    m["_i"] = np.arange(len(m))
    m["horizon_date"] = m["observation_date"] + pd.DateOffset(months=int(followup_months))
    j = m.merge(wd, on="project_key", how="left")
    hit = j["outcome_date"].notna() & (j["outcome_date"] > j["observation_date"]) & (j["outcome_date"] <= j["horizon_date"])
    flags = pd.Series(False, index=range(len(panel)))
    if hit.any():
        flags.iloc[j.loc[hit, "_i"].to_numpy()] = True
    return pd.Series(flags.to_numpy(), index=panel.index)


def assign_delay_labels(
    annual: pd.DataFrame,
    snaps: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    followup_months: int = FOLLOWUP_MONTHS,
    eia: pd.DataFrame | None = None,
) -> pd.DataFrame:
    known = last_known_cod_table(snaps)
    known = known.sort_values(["project_key", "observation_date", "source_name"]).drop_duplicates(
        ["project_key", "observation_date"], keep="first"
    )
    panel = annual.copy()
    panel["observation_date"] = pd.to_datetime(panel["observation_date"])
    panel = panel.merge(
        known[["project_key", "observation_date", "last_known_cod", "cod_at_entry"]],
        on=["project_key", "observation_date"],
        how="left",
    )
    panel = panel.rename(columns={"last_known_cod": "cod_at_t"})
    panel = attach_future_cod(panel, snaps, followup_months=followup_months, eia=eia)
    withdrawn = _withdrawn_in_window(panel, outcomes, followup_months=followup_months)

    later_any = snaps.copy()
    later_any["observation_date"] = pd.to_datetime(later_any["observation_date"])
    last_obs = later_any.groupby("project_key")["observation_date"].max().rename("project_last_obs")
    panel = panel.merge(last_obs, on="project_key", how="left")
    horizon = panel["observation_date"] + pd.DateOffset(months=int(followup_months))
    complete = withdrawn | panel["future_cod"].notna() | (pd.to_datetime(panel["project_last_obs"]) >= horizon)

    slip = [
        month_delta(fc, ct)
        for fc, ct in zip(panel["future_cod"], panel["cod_at_t"], strict=False)
    ]
    slip_s = pd.Series(slip, index=panel.index)
    event = np.where(
        withdrawn,
        "withdrawn",
        np.where(
            slip_s.notna(),
            "labeled",
            np.where(complete, "no_future_cod", "censored"),
        ),
    )
    slip_s = slip_s.where(~withdrawn, np.nan)

    panel["cod_slip_months_next_12m"] = slip_s
    panel["cod_slip_ge_12m"] = np.where(slip_s.notna(), (slip_s >= 12).astype("float64"), np.nan)
    panel["event_type"] = event
    panel["complete_followup"] = complete.astype(bool)
    panel["delay_from_original_months"] = [
        month_delta(fc, en) if pd.notna(fc) else month_delta(ct, en)
        for fc, ct, en in zip(panel["future_cod"], panel["cod_at_t"], panel["cod_at_entry"], strict=False)
    ]
    panel["followup_months"] = int(followup_months)
    return panel


def calendar_split(year: pd.Series) -> pd.Series:
    y = pd.to_numeric(year, errors="coerce")
    return pd.Series(
        np.where(
            y.between(2020, 2022),
            "train",
            np.where(y == 2023, "val", np.where(y == 2024, "test", np.where(y >= 2025, "score", "other"))),
        ),
        index=year.index,
    )


def is_gia_row(study_phase, post_gia_status) -> bool:
    sp = "" if pd.isna(study_phase) else str(study_phase)
    pg = "" if pd.isna(post_gia_status) else str(post_gia_status)
    return sp in GIA_PHASES or pg in ADVANCED_POST_GIA


def audit_label_counts(panel: pd.DataFrame) -> dict[str, Any]:
    df = panel.copy()
    year = pd.to_datetime(df["observation_date"]).dt.year
    labeled = df["cod_slip_months_next_12m"].notna()
    gia = [
        is_gia_row(sp, pg)
        for sp, pg in zip(df.get("study_phase", pd.Series(index=df.index)), df.get("post_gia_status"), strict=False)
    ]
    gia_s = pd.Series(gia, index=df.index)
    slip = pd.to_numeric(df["cod_slip_months_next_12m"], errors="coerce")
    mw = pd.to_numeric(df.get("capacity_mw"), errors="coerce").fillna(0.0)

    def _slice(mask: pd.Series) -> dict[str, Any]:
        sub = df.loc[mask]
        s = slip.loc[mask]
        w = mw.loc[mask]
        lab = s.notna()
        delayed = lab & (s >= 12)
        return {
            "n": int(mask.sum()),
            "complete_followup": int(sub["complete_followup"].fillna(False).sum()) if "complete_followup" in sub else 0,
            "labeled": int(lab.sum()),
            "withdrawn": int((sub["event_type"] == "withdrawn").sum()) if "event_type" in sub else 0,
            "median_slip": float(s.median()) if lab.any() else None,
            "share_ge_6m": float((s >= 6).mean()) if lab.any() else None,
            "share_ge_12m": float((s >= 12).mean()) if lab.any() else None,
            "share_ge_24m": float((s >= 24).mean()) if lab.any() else None,
            "delayed_mw": float(w.loc[delayed].sum()) if lab.any() else 0.0,
            "labeled_mw": float(w.loc[lab].sum()),
        }

    by_year = {int(y): _slice(year == y) for y in sorted(year.dropna().unique())}
    by_split = {str(s): _slice(df["split"] == s) for s in sorted(df["split"].dropna().unique())} if "split" in df else {}
    val_labeled = int(((df.get("split") == "val") & labeled).sum()) if "split" in df else int((year == 2023) & labeled).sum()
    return {
        "followup_months": int(df["followup_months"].iloc[0]) if "followup_months" in df.columns and len(df) else FOLLOWUP_MONTHS,
        "n_rows": int(len(df)),
        "have_cod_at_t": int(df["cod_at_t"].notna().sum()) if "cod_at_t" in df else 0,
        "by_year": by_year,
        "by_split": by_split,
        "val_labeled": val_labeled,
        "train_labeled": int(((df.get("split") == "train") & labeled).sum()) if "split" in df else None,
        "gia_labeled": _slice(gia_s & labeled),
        "gia_val_labeled": int((gia_s & labeled & (df.get("split") == "val" if "split" in df else year == 2023)).sum()),
        "event_counts": df["event_type"].value_counts(dropna=False).to_dict() if "event_type" in df else {},
        "neural_nets_ok": bool(val_labeled >= NEURAL_NET_MIN_VAL_LABELED),
        "neural_net_min_val_labeled": NEURAL_NET_MIN_VAL_LABELED,
        "note": (
            "Berkeley 2024 service dates are empty; follow-up uses the next non-null COD "
            f"within {FOLLOWUP_MONTHS} months (typically year-end t -> t+2). "
            "MISO operational_date is Appl In Service Date, not proven COD."
        ),
    }


def load_snapshots() -> pd.DataFrame:
    return pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")


def load_outcomes() -> pd.DataFrame:
    path = SILVER_DIR / "outcomes" / "project_outcomes.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_eia_matched() -> pd.DataFrame | None:
    path = SILVER_DIR / "enrichment" / "eia_860m_giq_matched.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return None
