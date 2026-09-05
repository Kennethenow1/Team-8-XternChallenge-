"""Shared type, date, status, technology, and location normalizers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.common.paths import STATUS_MAP_YAML, TECH_MAP_YAML

CAPACITY_EXTREME_MW = 5000.0

_STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def as_string_id(series: pd.Series) -> pd.Series:
    """Store identifiers as strings; never cast queue IDs to integers."""

    def _one(v: Any) -> str | None:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if pd.isna(v):
            return None
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        s = str(v).strip()
        if s.lower() in {"", "nan", "none", "null"}:
            return None
        # Strip trailing .0 from excel float-stringified ids
        if re.fullmatch(r"-?\d+\.0", s):
            return s[:-2]
        return s

    return series.map(_one)


def parse_date_with_precision(value: Any) -> tuple[pd.Timestamp | pd.NaT, str | None, str | None]:
    """
    Convert a value to a date, recording precision and parse errors.
    Year-only values become YYYY-01-01 with precision='year' (not pretended exact).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return pd.NaT, None, None

    if isinstance(value, pd.Timestamp):
        return value.normalize(), "day", None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        try:
            return pd.Timestamp(value).normalize(), "day", None
        except Exception as exc:  # noqa: BLE001
            return pd.NaT, None, f"datetime_convert:{exc}"

    s = str(value).strip()
    if s.lower() in {"", "nan", "none", "null", "nat"}:
        return pd.NaT, None, None

    # Year only
    if re.fullmatch(r"\d{4}", s):
        return pd.Timestamp(f"{s}-01-01"), "year", None

    # Year-month
    if re.fullmatch(r"\d{4}[-/]\d{1,2}", s):
        y, m = re.split(r"[-/]", s)
        return pd.Timestamp(int(y), int(m), 1), "month", None

    try:
        ts = pd.to_datetime(s, utc=False, errors="raise")
        if isinstance(ts, pd.DatetimeIndex):
            ts = ts[0]
        ts = pd.Timestamp(ts)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        return ts.normalize(), "day", None
    except Exception as exc:  # noqa: BLE001
        return pd.NaT, None, f"parse_error:{exc}"


def parse_date_series(series: pd.Series | pd.DataFrame, prefix: str) -> pd.DataFrame:
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    dates, precisions, errors = [], [], []
    for v in series.tolist():
        d, p, e = parse_date_with_precision(v)
        dates.append(d)
        precisions.append(p)
        errors.append(e)
    return pd.DataFrame(
        {
            prefix: dates,
            f"{prefix}_precision": precisions,
            f"{prefix}_parse_error": errors,
        }
    )


def to_numeric_mw(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def capacity_flags(capacity: pd.Series, component_sum: pd.Series | None = None) -> pd.DataFrame:
    cap = pd.to_numeric(capacity, errors="coerce")
    out = pd.DataFrame(
        {
            "capacity_negative": (cap < 0).fillna(False),
            "capacity_zero": (cap == 0).fillna(False),
            "capacity_extreme": (cap > CAPACITY_EXTREME_MW).fillna(False),
        }
    )
    if component_sum is not None:
        cs = pd.to_numeric(component_sum, errors="coerce")
        # Conflict when both present and differ by >10% relative or >5 MW absolute
        rel = (cap - cs).abs()
        conflict = (cap.notna() & cs.notna()) & ((rel > 5) & (rel > 0.1 * cap.abs().clip(lower=1)))
        out["component_capacity_conflict"] = conflict.fillna(False)
    else:
        out["component_capacity_conflict"] = False
    return out


def _norm_status_key(v: Any) -> str | None:
    if v is None or pd.isna(v):
        return None
    return re.sub(r"\s+", " ", str(v).strip().lower())


def map_status(raw: pd.Series, source_family: str) -> pd.DataFrame:
    cfg = load_yaml(STATUS_MAP_YAML)
    mapping = cfg.get(source_family, {}) | cfg.get("berkeley", {})
    # Prefer family-specific keys
    family_map = {k.lower(): v for k, v in cfg.get(source_family, {}).items()}
    fallback = {k.lower(): v for k, v in cfg.get("berkeley", {}).items()}

    raw_s = raw.map(_norm_status_key)
    clean = raw_s.map(lambda x: family_map.get(x) if x else None)
    clean = clean.fillna(raw_s.map(lambda x: fallback.get(x) if x else None))
    clean = clean.fillna("unknown")
    # Unmapped non-null raw that didn't hit maps already set to unknown above;
    # mark truly unmapped: if raw present and not in maps
    known = set(family_map) | set(fallback)
    unmapped = raw_s.notna() & ~raw_s.isin(known)
    clean = clean.where(~unmapped, other="unknown")

    return pd.DataFrame({"status_raw": raw_s, "status_clean": clean, "status": clean})


def status_consistency(
    status_clean: pd.Series,
    withdrawal_date: pd.Series,
    operational_date: pd.Series,
) -> pd.Series:
    flags = []
    for st, wd, od in zip(status_clean, withdrawal_date, operational_date, strict=False):
        parts = []
        wd_ok = pd.notna(wd)
        od_ok = pd.notna(od)
        if st == "withdrawn" and wd_ok:
            parts.append("confirmed_withdrawal")
        elif st == "withdrawn" and not wd_ok:
            parts.append("withdrawal_uncertain_timing")
        if st == "active" and wd_ok:
            parts.append("active_withdrawal_conflict")
        if od_ok:
            parts.append("operational_outcome")
        flags.append("|".join(parts) if parts else None)
    return pd.Series(flags, index=status_clean.index)


def canonicalize_technology_token(token: str, aliases: dict[str, str]) -> str:
    t = re.sub(r"\s+", " ", token.strip().lower())
    t = t.replace("_", " ")
    if t in aliases:
        return aliases[t]
    # try without spaces
    compact = t.replace(" ", "_")
    if compact in aliases:
        return aliases[compact]
    if "offshore" in t and "wind" in t:
        return "wind_offshore"
    if "wind" in t:
        return "wind_onshore"
    if "solar" in t or "pv" in t or "photo" in t:
        return "solar"
    if "batter" in t or "storage" in t or "bess" in t:
        return "battery"
    if "gas" in t:
        return "natural_gas"
    if "nuclear" in t:
        return "nuclear"
    if "hydro" in t:
        return "hydro"
    if t in {"", "nan", "none"}:
        return "unknown"
    return aliases.get(t, "other")


def parse_technology_fields(
    type_clean: pd.Series | None = None,
    type1: pd.Series | None = None,
    type2: pd.Series | None = None,
    type3: pd.Series | None = None,
    mw1: pd.Series | None = None,
    mw2: pd.Series | None = None,
    mw3: pd.Series | None = None,
    fuel_raw: pd.Series | None = None,
) -> pd.DataFrame:
    cfg = load_yaml(TECH_MAP_YAML)
    aliases = {str(k).lower(): v for k, v in cfg.get("aliases", {}).items()}

    n = len(type1) if type1 is not None else (len(fuel_raw) if fuel_raw is not None else 0)
    rows = []
    for i in range(n):
        comps: list[tuple[str, float | None]] = []
        raw_bits = []

        def add_type_mw(tval, mval):
            if tval is None or (isinstance(tval, float) and pd.isna(tval)) or pd.isna(tval):
                return
            tok = canonicalize_technology_token(str(tval), aliases)
            mw = None
            if mval is not None and not (isinstance(mval, float) and pd.isna(mval)) and not pd.isna(mval):
                try:
                    mw = float(mval)
                except (TypeError, ValueError):
                    mw = None
            comps.append((tok, mw))
            raw_bits.append(str(tval))

        if type1 is not None:
            add_type_mw(type1.iloc[i], mw1.iloc[i] if mw1 is not None else None)
        if type2 is not None:
            add_type_mw(type2.iloc[i], mw2.iloc[i] if mw2 is not None else None)
        if type3 is not None:
            add_type_mw(type3.iloc[i], mw3.iloc[i] if mw3 is not None else None)

        if not comps and fuel_raw is not None:
            fr = fuel_raw.iloc[i]
            if fr is not None and not pd.isna(fr):
                raw_bits.append(str(fr))
                text = str(fr)
                # split hybrids
                parts = re.split(r"\+|\/|&|,|\band\b", text, flags=re.IGNORECASE)
                parts = [p.strip() for p in parts if p and p.strip()]
                for p in parts or [text]:
                    comps.append((canonicalize_technology_token(p, aliases), None))

        if not comps and type_clean is not None:
            tc = type_clean.iloc[i]
            if tc is not None and not pd.isna(tc):
                raw_bits.append(str(tc))
                parts = re.split(r"\+|\/|&|,|\band\b", str(tc), flags=re.IGNORECASE)
                parts = [p.strip() for p in parts if p and p.strip()]
                for p in parts or [str(tc)]:
                    comps.append((canonicalize_technology_token(p, aliases), None))

        # Deduplicate tech keeping first MW
        seen = {}
        for tok, mw in comps:
            if tok not in seen:
                seen[tok] = mw
            elif seen[tok] is None and mw is not None:
                seen[tok] = mw

        techs = list(seen.keys())
        primary = techs[0] if techs else "unknown"
        secondary = techs[1] if len(techs) > 1 else None
        is_hybrid = int(len(techs) > 1)

        def mw_for(*names: str) -> float | None:
            for name in names:
                if name in seen and seen[name] is not None:
                    return seen[name]
            return None

        rows.append(
            {
                "technology_raw": " + ".join(raw_bits) if raw_bits else None,
                "technology_primary": primary,
                "technology_secondary": secondary,
                "is_hybrid": is_hybrid,
                "technology_count": len(techs) if techs else 0,
                "solar_mw": mw_for("solar"),
                "wind_mw": mw_for("wind_onshore", "wind_offshore"),
                "battery_mw": mw_for("battery"),
                "gas_mw": mw_for("natural_gas"),
                "storage_power_mw": mw_for("battery"),
            }
        )
    return pd.DataFrame(rows)


def normalize_state(series: pd.Series) -> pd.DataFrame:
    codes = []
    for v in series.tolist():
        if v is None or pd.isna(v):
            codes.append(None)
            continue
        s = str(v).strip()
        if re.fullmatch(r"[A-Za-z]{2}", s):
            codes.append(s.upper())
        else:
            codes.append(_STATE_NAME_TO_CODE.get(s.lower()))
    return pd.DataFrame({"state": series.map(lambda x: None if pd.isna(x) else str(x).strip()), "state_code": codes})


def clean_poi_name(name: Any) -> tuple[str | None, str | None]:
    if name is None or pd.isna(name):
        return None, None
    raw = str(name).strip()
    if raw.lower() in {"", "nan", "none"}:
        return None, None
    # Matching key: uppercase, collapse whitespace/punct, standardize kV
    key = raw.upper()
    key = re.sub(r"(\d+)\s*KV\b", r"\1KV", key)
    key = re.sub(r"[^\w\s]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    clean = re.sub(r"\s+", " ", raw).strip()
    return clean, key


def normalize_poi(series: pd.Series) -> pd.DataFrame:
    cleans, keys = [], []
    for v in series.tolist():
        c, k = clean_poi_name(v)
        cleans.append(c)
        keys.append(k)
    return pd.DataFrame({"poi_name_clean": cleans, "poi_key": keys})


def clean_text(series: pd.Series) -> pd.Series:
    def _c(v):
        if v is None or pd.isna(v):
            return None
        s = re.sub(r"\s+", " ", str(v).strip())
        return s if s.lower() not in {"", "nan", "none"} else None

    return series.map(_c)


def empty_canonical_frame(n: int = 0) -> pd.DataFrame:
    from src.common.canonical_schema import CANONICAL_COLUMNS

    return pd.DataFrame({c: [None] * n for c in CANONICAL_COLUMNS})


def quality_score_row(
    status_clean: str | None,
    capacity_mw: float | None,
    queue_date: Any,
    state_code: str | None,
    tech: str | None,
) -> float:
    score = 1.0
    if not status_clean or status_clean == "unknown":
        score -= 0.2
    if capacity_mw is None or (isinstance(capacity_mw, float) and pd.isna(capacity_mw)):
        score -= 0.2
    if pd.isna(queue_date):
        score -= 0.2
    if not state_code:
        score -= 0.1
    if not tech or tech == "unknown":
        score -= 0.1
    return max(0.0, round(score, 3))
