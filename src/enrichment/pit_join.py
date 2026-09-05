"""Point-in-time join helpers and rolling windows. Never zero-fill missing."""

from __future__ import annotations

import numpy as np
import pandas as pd


def status_value(value, status: str | None = None) -> tuple[object, str]:
    """
    Distinguish unavailable / not_applicable / genuine zero.
    Returns (stored_value, status) where status in {ok, unavailable, not_applicable, zero}.
    """
    if status is not None:
        return value, status
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return None, "unavailable"
    if value == 0 or value == 0.0:
        return 0, "zero"
    return value, "ok"


def asof_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_on: str,
    right_on: str,
    left_time: str = "observation_date",
    right_available: str = "available_date",
    suffixes: tuple[str, str] = ("", "_enr"),
) -> pd.DataFrame:
    """
    For each left row, take the latest right row with same key and
    right.available_date <= left.observation_date.
    """
    if right.empty:
        return left.copy()

    L = left.copy()
    R = right.copy()
    L[left_time] = pd.to_datetime(L[left_time])
    R[right_available] = pd.to_datetime(R[right_available])
    L["_row_id"] = np.arange(len(L))

    # merge_asof requires sorting by the on-key; within ties, by-keys must be ordered
    L = L.sort_values([left_time, left_on]).reset_index(drop=True)
    R = R.sort_values([right_available, right_on]).reset_index(drop=True)

    R = R.rename(columns={right_on: left_on, right_available: left_time})
    merged = pd.merge_asof(
        L,
        R,
        on=left_time,
        by=left_on,
        direction="backward",
        suffixes=suffixes,
        allow_exact_matches=True,
    )
    return merged.sort_values("_row_id").drop(columns=["_row_id"], errors="ignore")


def rolling_event_features(
    panel: pd.DataFrame,
    events: pd.DataFrame,
    *,
    panel_key: str,
    event_key: str,
    panel_time: str = "observation_date",
    event_time: str = "available_date",
    windows_days: list[int] | None = None,
    count_col: str = "event_count",
    source_available: bool = True,
) -> pd.DataFrame:
    """
    Count events in (t - W, t] per panel row.
    If source_available is False (table empty / not ingested), return nulls — not zeros.
    """
    windows_days = windows_days or [30, 90, 180, 365]
    out = panel[[panel_key, panel_time]].copy() if panel_key in panel.columns else panel.copy()
    out[panel_time] = pd.to_datetime(out[panel_time])

    if not source_available or events is None or events.empty:
        for w in windows_days:
            out[f"{count_col}_{w}d"] = pd.NA
            out[f"{count_col}_{w}d_status"] = "unavailable"
        return out

    E = events.copy()
    E[event_time] = pd.to_datetime(E[event_time])
    # vectorized per unique key
    counts = {w: [] for w in windows_days}
    statuses = {w: [] for w in windows_days}

    events_by_key = {k: g for k, g in E.groupby(event_key)}
    for key, t in zip(out[panel_key], out[panel_time], strict=False):
        eg = events_by_key.get(key)
        if eg is None or len(eg) == 0:
            for w in windows_days:
                counts[w].append(0)
                statuses[w].append("zero")
            continue
        times = eg[event_time].to_numpy()
        for w in windows_days:
            start = t - pd.Timedelta(days=w)
            n = int(((times > np.datetime64(start)) & (times <= np.datetime64(t))).sum())
            counts[w].append(n)
            statuses[w].append("zero" if n == 0 else "ok")

    for w in windows_days:
        out[f"{count_col}_{w}d"] = counts[w]
        out[f"{count_col}_{w}d_status"] = statuses[w]
    return out


def leakage_rows(
    panel: pd.DataFrame,
    enrichment: pd.DataFrame,
    *,
    panel_key: str,
    enr_key: str,
    panel_time: str = "observation_date",
    enr_available: str = "available_date",
    feature_source: str,
) -> pd.DataFrame:
    """Return rows that would leak if joined (available after observation)."""
    if enrichment.empty:
        return pd.DataFrame(
            columns=["feature_source", "panel_key", "observation_date", "available_date", "issue"]
        )
    P = panel[[panel_key, panel_time]].copy()
    E = enrichment[[enr_key, enr_available]].copy()
    P[panel_time] = pd.to_datetime(P[panel_time])
    E[enr_available] = pd.to_datetime(E[enr_available])
    m = P.merge(E, left_on=panel_key, right_on=enr_key, how="inner")
    bad = m[m[enr_available] > m[panel_time]].copy()
    if bad.empty:
        return pd.DataFrame(
            columns=["feature_source", "panel_key", "observation_date", "available_date", "issue"]
        )
    return pd.DataFrame(
        {
            "feature_source": feature_source,
            "panel_key": bad[panel_key],
            "observation_date": bad[panel_time],
            "available_date": bad[enr_available],
            "issue": "available_date_after_observation_date",
        }
    )
