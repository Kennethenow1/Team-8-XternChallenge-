"""Build enriched Gold panels via PIT joins (no model training)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.paths import GOLD_DIR, SILVER_DIR
from src.enrichment.pit_join import asof_join, leakage_rows
from src.enrichment.registry import ENRICHMENT_REPORTS, SILVER_ENRICHMENT, ensure_enrichment_dirs


def _read_enr(name: str) -> pd.DataFrame:
    path = SILVER_ENRICHMENT / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _safe_asof(panel: pd.DataFrame, enr: pd.DataFrame, left_on: str, right_on: str) -> pd.DataFrame:
    if enr.empty or left_on not in panel.columns:
        return panel
    # Drop rows with null join keys
    enr = enr[enr[right_on].notna()].copy()
    if enr.empty:
        return panel
    panel2 = panel[panel[left_on].notna()].copy()
    if panel2.empty:
        return panel
    try:
        return asof_join(panel2, enr, left_on=left_on, right_on=right_on)
    except Exception as exc:  # noqa: BLE001
        print(f"  asof join failed {left_on}: {exc}")
        return panel


def attach_queue_pressure_features(panel: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """same_poi_project_count, nearby_queue_mw, same_group_prior_withdrawal_rate — PIT from snapshots."""
    out = panel.copy()
    snaps = snaps.copy()
    snaps["observation_date"] = pd.to_datetime(snaps["observation_date"])
    snaps["capacity_mw"] = pd.to_numeric(snaps["capacity_mw"], errors="coerce")

    poi_n, poi_mw, grp_wd = [], [], []
    by_date = {d: g for d, g in snaps.groupby("observation_date")}

    for _, row in out.iterrows():
        od = pd.Timestamp(row["observation_date"])
        peers = by_date.get(od, snaps.iloc[0:0])
        peers = peers[peers["project_key"] != row["project_key"]]
        active = peers[peers["status_clean"] == "active"]
        poi = row.get("poi_key")
        if poi and "poi_key" in active.columns:
            same_poi = active[active["poi_key"] == poi]
            poi_n.append(len(same_poi))
            poi_mw.append(float(same_poi["capacity_mw"].sum(skipna=True)))
        else:
            poi_n.append(pd.NA)
            poi_mw.append(pd.NA)

        sg = row.get("study_group")
        if sg and "study_group" in snaps.columns:
            hist = snaps[
                (snaps["observation_date"] <= od)
                & (snaps["study_group"] == sg)
                & (snaps["project_key"] != row["project_key"])
            ]
            if len(hist):
                last = hist.sort_values("observation_date").groupby("project_key").tail(1)
                rate = float((last["status_clean"] == "withdrawn").mean())
                grp_wd.append(rate)
            else:
                grp_wd.append(pd.NA)
        else:
            grp_wd.append(pd.NA)

    out["same_poi_project_count"] = poi_n
    out["nearby_queue_mw"] = poi_mw
    out["same_group_prior_withdrawal_rate"] = grp_wd
    return out


def attach_macro_features(panel: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    miso_cols = [
        "miso_mean_demand_mw",
        "miso_peak_demand_mw",
        "miso_demand_yoy_pct",
        "miso_generation_yoy_pct",
        "miso_net_interchange_mw",
    ]
    if market.empty or "interest_rate_10y" not in market.columns:
        panel["interest_rate_at_entry"] = pd.NA
        panel["interest_rate_at_observation"] = pd.NA
        panel["interest_rate_change_since_entry"] = pd.NA
        panel["construction_cost_index_change_12m"] = pd.NA
        for c in miso_cols:
            panel[c] = pd.NA
        return panel

    from src.common.paths import SILVER_DIR

    m = market.dropna(subset=["available_date"]).copy()
    m["available_date"] = pd.to_datetime(m["available_date"])
    # Prefer month-end aggregates to speed joins
    if "year_month" in m.columns:
        agg = {
            "effective_date": "max",
            "available_date": "max",
            "interest_rate_10y": "last",
        }
        if "ppi_construction" in m.columns:
            agg["ppi_construction"] = "last"
        for c in miso_cols:
            if c in m.columns:
                agg[c] = "last"
        m = m.sort_values("available_date").groupby("year_month", as_index=False).agg(agg)
    m = m.sort_values("available_date")
    out = panel.copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"])

    # Attach queue_date from master if missing on panel
    if "queue_date" not in out.columns or out["queue_date"].isna().all():
        master = pd.read_parquet(SILVER_DIR / "projects" / "project_master.parquet")
        out = out.drop(columns=["queue_date"], errors="ignore").merge(
            master[["project_key", "queue_date"]], on="project_key", how="left"
        )

    m2 = m.copy()
    m2["join_zone"] = "MISO"
    out["join_zone"] = "MISO"
    merged = asof_join(
        out,
        m2,
        left_on="join_zone",
        right_on="join_zone",
        left_time="observation_date",
        right_available="available_date",
    )
    out["interest_rate_at_observation"] = (
        merged["interest_rate_10y"].values if "interest_rate_10y" in merged.columns else pd.NA
    )
    for c in miso_cols:
        out[c] = merged[c].values if c in merged.columns else pd.NA

    entry = out[["project_key", "queue_date"]].copy()
    entry["queue_date"] = pd.to_datetime(entry["queue_date"])
    entry["join_zone"] = "MISO"
    entry = entry.rename(columns={"queue_date": "observation_date"})
    ent_m = asof_join(
        entry.dropna(subset=["observation_date"]),
        m2,
        left_on="join_zone",
        right_on="join_zone",
        left_time="observation_date",
        right_available="available_date",
    )
    rate_map = dict(
        zip(ent_m["project_key"], ent_m["interest_rate_10y"] if "interest_rate_10y" in ent_m.columns else [])
    )
    out["interest_rate_at_entry"] = out["project_key"].map(rate_map)
    out["interest_rate_change_since_entry"] = (
        pd.to_numeric(out["interest_rate_at_observation"], errors="coerce")
        - pd.to_numeric(out["interest_rate_at_entry"], errors="coerce")
    )

    if "ppi_construction" in m.columns:
        m["ppi"] = pd.to_numeric(m["ppi_construction"], errors="coerce")
        m = m.sort_values("available_date")
        changes = []
        for t in out["observation_date"]:
            hist = m[m["available_date"] <= t]
            if len(hist) < 2:
                changes.append(pd.NA)
                continue
            cur = hist.iloc[-1]["ppi"]
            past = hist[hist["available_date"] <= t - pd.DateOffset(months=12)]
            if past.empty or pd.isna(cur) or pd.isna(past.iloc[-1]["ppi"]) or past.iloc[-1]["ppi"] == 0:
                changes.append(pd.NA)
            else:
                changes.append(float((cur - past.iloc[-1]["ppi"]) / past.iloc[-1]["ppi"] * 100))
        out["construction_cost_index_change_12m"] = changes
    else:
        out["construction_cost_index_change_12m"] = pd.NA

    out = out.drop(columns=["join_zone"], errors="ignore")
    return out


def attach_county_features(panel: pd.DataFrame, geo: pd.DataFrame, county_year: pd.DataFrame, weather: pd.DataFrame, policy: pd.DataFrame) -> pd.DataFrame:
    out = panel.merge(
        geo[["project_key", "county_fips", "miso_zone", "study_group", "poi_key"]],
        on="project_key",
        how="left",
        suffixes=("", "_geo"),
    )
    for c in ("poi_key", "study_group"):
        if f"{c}_geo" in out.columns:
            out[c] = out[c].fillna(out[f"{c}_geo"]) if c in out.columns else out[f"{c}_geo"]
            out = out.drop(columns=[f"{c}_geo"], errors="ignore")

    # county_year asof on county_fips
    if not county_year.empty and "county_fips" in out.columns:
        cy = county_year.copy()
        cy["available_date"] = pd.to_datetime(cy["available_date"])
        try:
            joined = asof_join(
                out.dropna(subset=["county_fips"]),
                cy,
                left_on="county_fips",
                right_on="county_fips",
            )
            for feat in ("fema_risk_score", "population", "rural_flag", "median_income"):
                if feat in joined.columns:
                    # reindex back — simpler: merge on project_key+obs from joined
                    out = out.drop(columns=[feat], errors="ignore")
                    tmp = joined[["project_key", "observation_date", feat]].drop_duplicates(
                        ["project_key", "observation_date"]
                    )
                    out = out.merge(tmp, on=["project_key", "observation_date"], how="left")
        except Exception as exc:  # noqa: BLE001
            print(f"  county_year join: {exc}")
            for feat in ("fema_risk_score", "population", "rural_flag"):
                out[feat] = pd.NA
    else:
        for feat in ("fema_risk_score", "population", "rural_flag"):
            out[feat] = pd.NA

    # weather 12m rolling from weather_county_month
    out["storm_events_12m"] = pd.NA
    out["storm_property_damage_12m"] = pd.NA
    out["extreme_weather_days_12m"] = pd.NA
    if not weather.empty and "county_fips" in out.columns:
        w = weather.copy()
        w["available_date"] = pd.to_datetime(w["available_date"])
        w["effective_date"] = pd.to_datetime(w.get("effective_date", w["available_date"]))
        for i, row in out.iterrows():
            cf = row.get("county_fips")
            t = pd.Timestamp(row["observation_date"])
            if pd.isna(cf):
                continue
            hist = w[
                (w["county_fips"] == cf)
                & (w["available_date"] <= t)
                & (w["effective_date"] > t - pd.DateOffset(months=12))
            ]
            if hist.empty:
                # source exists but no events in window → genuine zero if any weather ever for county
                ever = w[(w["county_fips"] == cf) & (w["available_date"] <= t)]
                if ever.empty:
                    continue
                out.at[i, "storm_events_12m"] = 0
                out.at[i, "storm_property_damage_12m"] = 0
                out.at[i, "extreme_weather_days_12m"] = 0
            else:
                out.at[i, "storm_events_12m"] = pd.to_numeric(hist["storm_events"], errors="coerce").sum()
                out.at[i, "storm_property_damage_12m"] = pd.to_numeric(
                    hist["storm_property_damage"], errors="coerce"
                ).sum()
                out.at[i, "extreme_weather_days_12m"] = pd.to_numeric(
                    hist["extreme_weather_days"], errors="coerce"
                ).sum()

    # energy community
    out["energy_community_eligible"] = pd.NA
    if not policy.empty and "county_fips" in out.columns:
        p = policy.copy()
        p["available_date"] = pd.to_datetime(p["available_date"])
        eligible = set(
            p.loc[p["energy_community_eligible"].astype(str).isin(["1", "1.0", "True", "true"]), "county_fips"]
            .astype(str)
            .str.zfill(5)
        )
        # only if available_date <= obs
        def _ec(row):
            cf = row.get("county_fips")
            if pd.isna(cf):
                return pd.NA
            cf = str(cf).zfill(5)
            avail = p[p["county_fips"].astype(str).str.zfill(5) == cf]
            avail = avail[avail["available_date"] <= pd.Timestamp(row["observation_date"])]
            if avail.empty:
                return pd.NA
            return int(cf in eligible)

        out["energy_community_eligible"] = out.apply(_ec, axis=1)

    return out


def attach_developer_features(panel: pd.DataFrame, dev_x: pd.DataFrame, dq: pd.DataFrame) -> pd.DataFrame:
    out = panel.merge(dev_x[["project_key", "developer_id"]], on="project_key", how="left")
    feats = [
        "developer_active_project_count",
        "developer_total_active_mw",
        "developer_prior_completion_rate",
        "developer_prior_withdrawal_rate",
    ]
    for c in feats:
        out[c] = pd.NA

    if dq.empty or out["developer_id"].isna().all():
        return out

    dq = dq.copy()
    dq["available_date"] = pd.to_datetime(dq["available_date"])
    dq["developer_id"] = dq["developer_id"].astype(str)
    try:
        sub = out.dropna(subset=["developer_id"]).copy()
        sub["developer_id"] = sub["developer_id"].astype(str)
        sub["observation_date"] = pd.to_datetime(sub["observation_date"])
        sub["_ix"] = sub.index
        joined = asof_join(sub, dq, left_on="developer_id", right_on="developer_id")
        for f in feats:
            # Right-side columns from enrichment get "_enr" suffix when left already has the name
            col = f"{f}_enr" if f"{f}_enr" in joined.columns else f
            if col not in joined.columns:
                continue
            out.loc[joined["_ix"].values, f] = pd.to_numeric(joined[col], errors="coerce").values
    except Exception as exc:  # noqa: BLE001
        print(f"  developer join: {exc}")
    return out


def _dpp_gold_eligible(study: pd.DataFrame) -> pd.DataFrame:
    """Keep high-confidence / table-backed DPP rows that have capacity or cost."""
    if study.empty:
        return study
    s = study.copy()
    conf = pd.to_numeric(s["extraction_confidence"], errors="coerce") if "extraction_confidence" in s.columns else pd.Series(np.nan, index=s.index)
    method = s["extraction_method"].astype(str).str.lower() if "extraction_method" in s.columns else pd.Series("", index=s.index)
    high = conf.fillna(0) >= 0.85
    table = method.str.contains("table", na=False)
    has_cap = pd.to_numeric(s["capacity_mw"], errors="coerce").notna() if "capacity_mw" in s.columns else False
    has_cost = False
    for c in ("project_cost", "network_upgrade_cost", "upgrade_cost_usd"):
        if c in s.columns:
            has_cost = has_cost | pd.to_numeric(s[c], errors="coerce").notna()
    return s[(high | table) & (has_cap | has_cost)].copy()


def attach_study_capacity_features(panel: pd.DataFrame, study: pd.DataFrame) -> pd.DataFrame:
    """
    PIT DPP / study features as of observation_date.
    Gold uses high-confidence / table rows with capacity or cost only.
    Derived multi-event fields only when ≥2 dated eligible events exist;
    otherwise left null (not zero-filled).
    """
    out = panel.copy()
    for col in [
        "capacity_reduction_pct",
        "upgrade_cost_per_mw",
        "network_upgrade_cost",
        "study_delay_days",
        "restudy_count",
        "cost_change_since_previous_study",
        "dpp_event_count_to_date",
        "latest_study_phase",
    ]:
        out[col] = pd.NA

    if study.empty or "project_key" not in study.columns:
        return out

    s = _dpp_gold_eligible(study)
    print(f"  DPP gold-eligible events: {len(s)} / {len(study)}")
    if s.empty:
        return out

    if "available_date" not in s.columns and "report_date" in s.columns:
        s["available_date"] = s["report_date"]
    if "available_date" not in s.columns and "event_date" in s.columns:
        s["available_date"] = s["event_date"]
    s["available_date"] = pd.to_datetime(s["available_date"], errors="coerce")
    s = s[s["available_date"].notna() & s["project_key"].notna()].copy()
    if s.empty:
        return out

    # Prefer project_cost / network_upgrade_cost for cost series
    cost_col = None
    for c in ("project_cost", "network_upgrade_cost", "upgrade_cost_usd"):
        if c in s.columns:
            cost_col = c
            break
    if cost_col:
        s["_cost"] = pd.to_numeric(s[cost_col], errors="coerce")
    else:
        s["_cost"] = pd.NA
    if "capacity_mw" in s.columns:
        s["_cap"] = pd.to_numeric(s["capacity_mw"], errors="coerce")
    else:
        s["_cap"] = pd.NA
    if "capacity_reduction_mw" in s.columns:
        s["_cred"] = pd.to_numeric(s["capacity_reduction_mw"], errors="coerce")
    else:
        s["_cred"] = pd.NA
    phase_col = "study_phase" if "study_phase" in s.columns else ("phase" if "phase" in s.columns else None)

    # Deduplicate same project/date keeping richest cost/capacity row
    s = s.sort_values(
        ["project_key", "available_date", "_cost", "_cap"],
        ascending=[True, True, False, False],
    )
    s = s.drop_duplicates(subset=["project_key", "available_date"], keep="first")

    feat_rows = []
    for pk, g in s.groupby("project_key", sort=False):
        g = g.reset_index(drop=True)
        dates = g["available_date"]
        costs = g["_cost"]
        caps = g["_cap"]
        for i in range(len(g)):
            hist = g.iloc[: i + 1]
            n = len(hist)
            delay = pd.NA
            restudy = pd.NA
            cost_chg = pd.NA
            cap_red_pct = pd.NA
            if n >= 2:
                delay = int((hist["available_date"].iloc[-1] - hist["available_date"].iloc[0]).days)
                if phase_col:
                    restudy = int(
                        hist[phase_col].astype(str).str.contains("restudy", case=False, na=False).sum()
                    )
                else:
                    restudy = 0
                c_prev, c_cur = costs.iloc[-2], costs.iloc[-1]
                if pd.notna(c_prev) and pd.notna(c_cur):
                    cost_chg = float(c_cur) - float(c_prev)
                if pd.notna(caps.iloc[0]) and float(caps.iloc[0]) > 0 and pd.notna(caps.iloc[-1]):
                    cap_red_pct = float((caps.iloc[0] - caps.iloc[-1]) / caps.iloc[0] * 100.0)
                elif pd.notna(hist["_cred"].iloc[-1]) and pd.notna(caps.iloc[-1]) and float(caps.iloc[-1] or 0) > 0:
                    cap_red_pct = float(hist["_cred"].iloc[-1]) / float(caps.iloc[-1]) * 100.0
            upg = pd.NA
            if pd.notna(costs.iloc[-1]) and pd.notna(caps.iloc[-1]) and float(caps.iloc[-1] or 0) > 0:
                upg = float(costs.iloc[-1]) / float(caps.iloc[-1])
            feat_rows.append(
                {
                    "project_key": pk,
                    "available_date": dates.iloc[i],
                    "dpp_event_count_to_date": n,
                    "study_delay_days": delay,
                    "restudy_count": restudy,
                    "cost_change_since_previous_study": cost_chg,
                    "capacity_reduction_pct": cap_red_pct,
                    "upgrade_cost_per_mw": upg,
                    "network_upgrade_cost": costs.iloc[-1],
                    "latest_study_phase": hist[phase_col].iloc[-1] if phase_col else pd.NA,
                    "effective_date": dates.iloc[i],
                }
            )

    feats = pd.DataFrame(feat_rows)
    if feats.empty:
        return out
    try:
        joined = asof_join(out, feats, left_on="project_key", right_on="project_key")
        for f in [
            "capacity_reduction_pct",
            "upgrade_cost_per_mw",
            "network_upgrade_cost",
            "study_delay_days",
            "restudy_count",
            "cost_change_since_previous_study",
            "dpp_event_count_to_date",
            "latest_study_phase",
        ]:
            col = f"{f}_enr" if f"{f}_enr" in joined.columns else f
            if col in joined.columns:
                out[f] = joined[col].values
    except Exception as exc:  # noqa: BLE001
        print(f"  study join: {exc}")
    return out


def attach_null_skeleton_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Features from registered_empty sources — null with unavailable semantics."""
    out = panel.copy()
    null_feats = [
        "upgrade_cost_change_pct",
        "distance_to_transmission_km",
        "local_congestion_mean_12m",
        "local_congestion_volatility_12m",
        "news_count_30d",
        "news_count_90d",
        "negative_news_count_90d",
        "opposition_event_count_180d",
        "permit_positive_count_180d",
        "financing_positive_count_180d",
        "news_sentiment_mean_90d",
        "days_since_last_positive_event",
        "days_since_last_negative_event",
        "solar_resource_percentile",
        "wind_resource_percentile",
        "wetlands_overlap_pct",
        "distance_to_wetlands_km",
        "drought_months_12m",
        "county_gdp_growth",
        "construction_employment_growth",
        "expected_incremental_load_mw",
        "developer_financing_event_180d",
        "developer_distress_event_180d",
    ]
    # Only mark unavailable when still entirely missing (DPP may have filled some).
    for f in ["study_delay_days", "restudy_count"]:
        if f not in out.columns:
            out[f] = pd.NA
        if out[f].isna().all():
            out[f"{f}_status"] = "unavailable"
        elif f"{f}_status" not in out.columns:
            out[f"{f}_status"] = np.where(out[f].notna(), "ok", "unavailable")

    for f in null_feats:
        if f not in out.columns:
            out[f] = pd.NA
            out[f"{f}_status"] = "unavailable"
    return out


def build_enriched_panels() -> dict[str, pd.DataFrame]:
    ensure_enrichment_dirs()
    annual = pd.read_parquet(GOLD_DIR / "annual_withdrawal_training" / "annual_withdrawal_training.parquet")
    current = pd.read_parquet(GOLD_DIR / "current_miso_scoring" / "current_miso_scoring.parquet")
    snaps = pd.read_parquet(SILVER_DIR / "snapshots" / "project_snapshots.parquet")
    geo = pd.read_parquet(SILVER_DIR / "crosswalks" / "geo_crosswalk.parquet")
    try:
        dev_x = pd.read_parquet(SILVER_DIR / "crosswalks" / "developer_crosswalk.parquet")
    except Exception:  # noqa: BLE001
        dev_x = pd.DataFrame(columns=["project_key", "developer_id"])

    market = _read_enr("market_zone_month")
    county_year = _read_enr("county_year")
    weather = _read_enr("weather_county_month")
    policy = _read_enr("policy_state_date")
    dq = _read_enr("developer_quarter")
    study = _read_enr("miso_dpp_events")
    if study.empty:
        study = _read_enr("study_events")
    print(f"  study/DPP events for Gold join: {len(study)}")

    def enrich(panel: pd.DataFrame) -> pd.DataFrame:
        p = panel.copy()
        p["observation_date"] = pd.to_datetime(p["observation_date"])
        p = attach_county_features(p, geo, county_year, weather, policy)
        p = attach_queue_pressure_features(p, snaps)
        p = attach_macro_features(p, market)
        p = attach_developer_features(p, dev_x, dq)
        p = attach_study_capacity_features(p, study)
        p = attach_null_skeleton_features(p)
        return p

    print("Enriching annual panel...")
    annual_e = enrich(annual)
    print("Enriching current scoring...")
    current_e = enrich(current)

    annual_path = GOLD_DIR / "withdrawal_panel_enriched.parquet"
    current_path = GOLD_DIR / "current_miso_scoring_enriched.parquet"
    annual_e.to_parquet(annual_path, index=False)
    current_e.to_parquet(current_path, index=False)
    annual_e.to_csv(GOLD_DIR / "withdrawal_panel_enriched.csv", index=False)
    current_e.to_csv(GOLD_DIR / "current_miso_scoring_enriched.csv", index=False)

    # Leakage audit — structural check on enrichment tables
    audits = []
    for name, key in [
        ("market_zone_month", "geographic_key"),
        ("county_year", "county_fips"),
        ("weather_county_month", "county_fips"),
        ("developer_quarter", "developer_id"),
        ("study_events", "project_key"),
        ("policy_state_date", "county_fips"),
    ]:
        enr = _read_enr(name)
        if enr.empty:
            continue
        # Build panel keys for audit
        if key == "project_key":
            panel_keys = annual_e[["project_key", "observation_date"]]
            audits.append(
                leakage_rows(
                    panel_keys, enr, panel_key="project_key", enr_key="project_key", feature_source=name
                )
            )
        elif key == "developer_id" and "developer_id" in annual_e.columns:
            panel_keys = annual_e[["developer_id", "observation_date"]].dropna()
            if len(panel_keys) and "developer_id" in enr.columns:
                audits.append(
                    leakage_rows(
                        panel_keys,
                        enr,
                        panel_key="developer_id",
                        enr_key="developer_id",
                        feature_source=name,
                    )
                )
        elif key in {"county_fips", "geographic_key"} and "county_fips" in annual_e.columns:
            pk = "county_fips" if "county_fips" in enr.columns else "geographic_key"
            panel_keys = annual_e[["county_fips", "observation_date"]].dropna().rename(
                columns={"county_fips": pk}
            )
            if len(panel_keys) and pk in enr.columns:
                audits.append(
                    leakage_rows(panel_keys, enr, panel_key=pk, enr_key=pk, feature_source=name)
                )

    audit = pd.concat(audits, ignore_index=True) if audits else pd.DataFrame(
        columns=["feature_source", "panel_key", "observation_date", "available_date", "issue"]
    )
    # Note: leakage_rows finds pairs where available > obs; for asof we don't use those.
    # Flag count for report — true leakage would be if we incorrectly joined them.
    audit_path = ENRICHMENT_REPORTS / "leakage_audit_enrichment.csv"
    audit.to_csv(audit_path, index=False)
    print(f"enriched annual={len(annual_e)} current={len(current_e)} leakage_candidate_pairs={len(audit)}")
    return {"annual": annual_e, "current": current_e, "audit": audit}


if __name__ == "__main__":
    build_enriched_panels()
