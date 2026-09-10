"""Assemble ChatGPT-safe risk cards from scores + peripherals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.gold.cod_delay import is_gia_row
from src.common.paths import REPO_ROOT
from src.modeling.eval_protocol import SELECTION_SPLIT
from src.modeling.model_registry import load_capacity_mw
from src.modeling.platinum3.context import join_project_facts, pile_asof, load_series
from src.modeling.platinum3.playbooks import PLAYBOOKS, playbook_ids_for
from src.modeling.platinum3.schema import (
    DEFAULT_THRESHOLDS,
    DO_NOT_CLAIM,
    RISK_CODES,
    SCHEMA_VERSION,
    SEVERITY_ORDER,
)
from src.modeling.platinum3.scorer import QuitScorer, load_split_xy, resolve_scorer
from src.modeling.platinum3.scenarios import SCENARIOS, apply_scenario, scenario_names

RESULTS_DIR = REPO_ROOT / "platinum3" / "results"


def _json_float(x) -> float | None:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else v


def train_thresholds(X_tr: pd.DataFrame) -> dict[str, float]:
    t = dict(DEFAULT_THRESHOLDS)
    if "developer_prior_withdrawal_rate" in X_tr.columns:
        s = pd.to_numeric(X_tr["developer_prior_withdrawal_rate"], errors="coerce")
        q = float(s.quantile(t["developer_serial_quantile"]))
        if np.isfinite(q):
            t["developer_serial"] = q
    if "fema_risk_score" in X_tr.columns:
        s = pd.to_numeric(X_tr["fema_risk_score"], errors="coerce")
        q = float(s.quantile(t["fema_high_quantile"]))
        if np.isfinite(q):
            t["fema_high"] = q
    if "network_upgrade_cost" in X_tr.columns:
        s = pd.to_numeric(X_tr["network_upgrade_cost"], errors="coerce")
        q = float(s.quantile(t["upgrade_cost_quantile"]))
        if np.isfinite(q):
            t["upgrade_cost_high"] = q
    t.setdefault("developer_serial", 0.5)
    t.setdefault("fema_high", 75.0)
    t.setdefault("upgrade_cost_high", float("nan"))
    return t


def _flag_row(x: pd.Series, facts: pd.Series, p_quit: float, pile: dict[str, Any], thresholds: dict[str, float], *, force_pile_crowded: bool) -> dict[str, Any]:
    p = float(p_quit) if np.isfinite(p_quit) else float("nan")
    restudy = pd.to_numeric(pd.Series([x.get("restudy_count")]), errors="coerce").iloc[0]
    fema = pd.to_numeric(pd.Series([x.get("fema_risk_score")]), errors="coerce").iloc[0]
    dev = pd.to_numeric(pd.Series([x.get("developer_prior_withdrawal_rate")]), errors="coerce").iloc[0]
    cost = pd.to_numeric(pd.Series([x.get("network_upgrade_cost")]), errors="coerce").iloc[0]
    passed = pd.to_numeric(pd.Series([x.get("service_date_passed")]), errors="coerce").iloc[0]
    months = pd.to_numeric(pd.Series([x.get("months_until_service")]), errors="coerce").iloc[0]
    gia = facts.get("is_gia")
    if pd.isna(gia):
        gia = False
    else:
        gia = bool(gia)
    gia = bool(gia or is_gia_row(x.get("study_phase"), facts.get("post_gia_status") if "post_gia_status" in facts.index else None))
    pile_pct = pile.get("pile_percentile_pit")
    crowded = bool(force_pile_crowded) or (
        pile_pct is not None and float(pile_pct) >= float(thresholds["pile_crowded_percentile"])
    )
    ecomm = facts.get("energy_community_eligible")
    return {
        "high_quit_risk": bool(np.isfinite(p) and p >= thresholds["p_quit_high"]),
        "medium_quit_risk": bool(np.isfinite(p) and p >= thresholds["p_quit_medium"]),
        "is_gia": gia,
        "cod_already_slipped": bool((pd.notna(passed) and passed >= 1) or (pd.notna(months) and months < 0)),
        "developer_serial": bool(pd.notna(dev) and dev >= thresholds["developer_serial"]),
        "restudy_on_record": bool(pd.notna(restudy) and restudy >= 1),
        "hazard_high": bool(pd.notna(fema) and fema >= thresholds["fema_high"]),
        "upgrade_cost_high": bool(
            pd.notna(cost) and np.isfinite(thresholds.get("upgrade_cost_high", float("nan"))) and cost >= thresholds["upgrade_cost_high"]
        ),
        "pile_crowded": crowded,
        "energy_community": bool(pd.notna(ecomm) and bool(ecomm)),
    }


def _risks_from_flags(flags: dict[str, Any], p_quit: float, thresholds: dict[str, float]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    def add(code: str, severity: str, evidence: str) -> None:
        risks.append(
            {
                "code": code,
                "severity": severity,
                "evidence": evidence,
                "meaning": RISK_CODES[code],
            }
        )

    p = _json_float(p_quit)
    if flags.get("high_quit_risk"):
        add("abandonment", "high", f"P(quit 12m)={p:.3f} ≥ {thresholds['p_quit_high']}")
    elif flags.get("medium_quit_risk"):
        add("abandonment", "medium", f"P(quit 12m)={p:.3f} ≥ {thresholds['p_quit_medium']}")
    if flags.get("pile_crowded"):
        add("system_congestion", "high" if flags.get("pile_crowded") else "medium", "Delayed-MW pile at/above PIT 75th percentile (or scenario override).")
    if flags.get("is_gia"):
        add("gia_execution", "medium", "GIA / IA as-of this observation.")
    if flags.get("cod_already_slipped"):
        add("cod_already_slipped", "high", "service_date_passed or months_until_service < 0 (current fact).")
    if flags.get("developer_serial"):
        add("developer_serial_quit", "medium", f"developer_prior_withdrawal_rate ≥ train p75 ({thresholds['developer_serial']:.3f}).")
    if flags.get("restudy_on_record"):
        add("restudy_friction", "medium", "restudy_count ≥ 1.")
    if flags.get("hazard_high"):
        add("hazard_exposure", "low", f"fema_risk_score ≥ train p75 ({thresholds['fema_high']:.1f}).")
    if flags.get("upgrade_cost_high"):
        add("cost_pressure", "medium", "network_upgrade_cost ≥ train p75.")
    if flags.get("energy_community"):
        add("policy_incentive", "low", "energy_community_eligible is true.")
    risks.sort(key=lambda r: -SEVERITY_ORDER.get(r["severity"], 0))
    return risks


def _card(
    *,
    meta_row: pd.Series,
    facts: pd.Series,
    x: pd.Series,
    p_raw: float,
    p_cal: float | None,
    p_scenario: float,
    pile: dict[str, Any],
    scenario: dict[str, Any],
    scorer: QuitScorer,
    thresholds: dict[str, float],
    force_pile_crowded: bool,
) -> dict[str, Any]:
    p_use = p_cal if p_cal is not None and np.isfinite(p_cal) else p_raw
    flags = _flag_row(x, facts, p_use if scenario.get("name") == "baseline" else p_scenario, pile, thresholds, force_pile_crowded=force_pile_crowded)
    # Risks under the scenario use scenario P(quit) for abandonment; other flags from (possibly overlaid) X + facts.
    risks = _risks_from_flags(flags, p_scenario if scenario.get("name") != "baseline" else p_use, thresholds)
    od = pd.Timestamp(meta_row["observation_date"])
    cap = facts.get("capacity_mw")
    pile_out = dict(pile)
    if force_pile_crowded:
        pile_out = dict(pile)
        pile_out["pile_percentile_pit"] = max(float(pile.get("pile_percentile_pit") or 0.0), 0.95)
        pile_out["note"] = (pile.get("note") or "") + " Scenario high_system_delay forced crowded."
    return {
        "schema_version": SCHEMA_VERSION,
        "project_key": str(meta_row["project_key"]),
        "observation_date": str(od.date()),
        "capacity_mw": _json_float(cap),
        "study_phase": None if pd.isna(x.get("study_phase")) else str(x.get("study_phase")),
        "technology_primary": None if pd.isna(x.get("technology_primary")) else str(x.get("technology_primary")),
        "state_code": None if pd.isna(x.get("state_code")) else str(x.get("state_code")),
        "poi_name": None if pd.isna(facts.get("poi_name")) else str(facts.get("poi_name")),
        "p_quit_12m_raw": _json_float(p_raw),
        "p_quit_12m": _json_float(p_use),
        "p_quit_source": scorer.source,
        "calibration_note": scorer.calibration_note,
        "pile": pile_out,
        "flags": flags,
        "scenario": {"name": scenario["name"], "note": scenario["note"]},
        "p_quit_under_scenario": _json_float(p_scenario),
        "delta_p_quit": _json_float((p_scenario - p_use) if np.isfinite(p_scenario) and np.isfinite(p_use) else None),
        "risks": risks,
        "playbook_ids": playbook_ids_for([r["code"] for r in risks]),
        "do_not_claim": list(DO_NOT_CLAIM),
    }


def build_risk_cards(
    *,
    split: str = SELECTION_SPLIT,
    scenarios: list[str] | None = None,
    scorer: QuitScorer | None = None,
) -> dict[str, Any]:
    if split == "test":
        raise RuntimeError("test is sealed")
    scorer = scorer or resolve_scorer()
    X, y, meta = load_split_xy(split)
    X_tr, _, _ = load_split_xy("train")
    thresholds = train_thresholds(X_tr)
    facts = join_project_facts(meta)
    facts.index = meta.index
    cap = load_capacity_mw(meta)
    if "capacity_mw" not in facts.columns or facts["capacity_mw"].isna().all():
        facts = facts.copy()
        facts["capacity_mw"] = cap.to_numpy()

    names = scenarios or scenario_names()
    series = load_series()
    pile_cache: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    raw_base, cal_base = scorer.predict(X)
    p_base = cal_base if cal_base is not None else raw_base

    X_by_scenario: dict[str, pd.DataFrame] = {}
    scenario_scores: dict[str, np.ndarray] = {}
    for name in names:
        Xs, spec = apply_scenario(X, name)
        X_by_scenario[name] = Xs
        raw_s, cal_s = scorer.predict(Xs)
        scenario_scores[name] = np.asarray(cal_s if cal_s is not None else raw_s, dtype=float)

    for i, idx in enumerate(meta.index):
        od = pd.Timestamp(meta.loc[idx, "observation_date"])
        cache_key = str(od.date())
        if cache_key not in pile_cache:
            pile_cache[cache_key] = pile_asof(od, series)
        pile = pile_cache[cache_key]
        x = X.loc[idx]
        fact = facts.loc[idx]
        meta_row = meta.loc[idx]
        p_raw = float(raw_base[i])
        p_cal = None if cal_base is None else float(cal_base[i])
        p_use = float(p_base[i])
        for name in names:
            spec = SCENARIOS[name]
            x_sc = X_by_scenario[name].loc[idx]
            p_s = float(scenario_scores[name][i])
            cards.append(
                _card(
                    meta_row=meta_row,
                    facts=fact,
                    x=x_sc if spec.get("changes_features") else x,
                    p_raw=p_raw,
                    p_cal=p_cal,
                    p_scenario=p_s,
                    pile=pile,
                    scenario=spec,
                    scorer=scorer,
                    thresholds=thresholds,
                    force_pile_crowded=bool(spec.get("force_pile_crowded")),
                )
            )

    deltas = []
    for name in names:
        if name == "baseline":
            continue
        d = scenario_scores[name] - np.asarray(p_base, dtype=float)
        deltas.append(
            {
                "scenario": name,
                "mean_delta_p": float(np.nanmean(d)),
                "median_delta_p": float(np.nanmedian(d)),
                "share_up": float(np.nanmean(d > 1e-6)),
                "n": int(np.isfinite(d).sum()),
            }
        )

    y_num = pd.to_numeric(y, errors="coerce")
    audit = meta.copy()
    audit["y_true"] = y_num.to_numpy()
    audit["p_quit_12m_raw"] = raw_base
    audit["p_quit_12m"] = p_base
    audit["capacity_mw"] = facts["capacity_mw"].to_numpy()
    # Labels stay in the team audit file only — never in GPT cards.
    return {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "test_sealed": True,
        "scorer_source": scorer.source,
        "calibration_note": scorer.calibration_note,
        "thresholds": thresholds,
        "n_rows": int(len(meta)),
        "n_cards": len(cards),
        "scenarios": names,
        "scenario_sensitivity_val_only": deltas if split == "val" else [],
        "cards": cards,
        "audit": audit if split == "val" else None,
        "labels_excluded_from_cards": True,
    }


def _pick_samples(cards: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    base = [c for c in cards if c.get("scenario", {}).get("name") == "baseline"]
    if not base:
        return cards[:n]
    scored = sorted(base, key=lambda c: -(c.get("p_quit_12m") or 0.0))
    picks = []
    if scored:
        picks.append(scored[0]["project_key"])
    gia = next((c for c in base if c.get("flags", {}).get("is_gia")), None)
    if gia and gia["project_key"] not in picks:
        picks.append(gia["project_key"])
    slipped = next((c for c in base if c.get("flags", {}).get("cod_already_slipped")), None)
    if slipped and slipped["project_key"] not in picks:
        picks.append(slipped["project_key"])
    while len(picks) < min(n, len(scored)):
        k = scored[len(picks)]["project_key"]
        if k not in picks:
            picks.append(k)
        else:
            break
    keys = set(picks)
    return [c for c in cards if c["project_key"] in keys]


def write_risk_card_bundle(bundle: dict[str, Any], dest: Path | None = None) -> dict[str, str]:
    dest = dest or RESULTS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "models").mkdir(parents=True, exist_ok=True)
    cards = bundle["cards"]
    split = bundle["split"]
    jsonl_path = dest / f"{split}_risk_cards.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for c in cards:
            fh.write(json.dumps(c, default=str) + "\n")
    flat_rows = []
    for c in cards:
        pile = c.get("pile") or {}
        flags = c.get("flags") or {}
        flat_rows.append(
            {
                "project_key": c.get("project_key"),
                "observation_date": c.get("observation_date"),
                "scenario": (c.get("scenario") or {}).get("name"),
                "capacity_mw": c.get("capacity_mw"),
                "study_phase": c.get("study_phase"),
                "p_quit_12m_raw": c.get("p_quit_12m_raw"),
                "p_quit_12m": c.get("p_quit_12m"),
                "p_quit_under_scenario": c.get("p_quit_under_scenario"),
                "delta_p_quit": c.get("delta_p_quit"),
                "delayed_mw_now": pile.get("delayed_mw_now"),
                "delayed_mw_h3": pile.get("delayed_mw_h3"),
                "delayed_mw_h12": pile.get("delayed_mw_h12"),
                "pile_percentile_pit": pile.get("pile_percentile_pit"),
                "risk_codes": "|".join(r.get("code", "") for r in (c.get("risks") or [])),
                "playbook_ids": "|".join(c.get("playbook_ids") or []),
                **{f"flag_{k}": v for k, v in flags.items()},
            }
        )
    parquet_path = dest / f"{split}_risk_cards.parquet"
    pd.DataFrame(flat_rows).to_parquet(parquet_path, index=False)
    samples = _pick_samples(cards)
    (dest / "sample_cards.json").write_text(json.dumps(samples, indent=2, default=str), encoding="utf-8")
    schema_doc = {
        "schema_version": SCHEMA_VERSION,
        "risk_codes": RISK_CODES,
        "do_not_claim": DO_NOT_CLAIM,
        "playbooks": PLAYBOOKS,
        "scenarios": {k: {kk: vv for kk, vv in v.items() if kk != "apply"} for k, v in SCENARIOS.items()},
        "thresholds": bundle.get("thresholds"),
        "scorer_source": bundle.get("scorer_source"),
        "calibration_note": bundle.get("calibration_note"),
        "labels_excluded_from_cards": True,
        "test_sealed": True,
    }
    (dest / "schema.json").write_text(json.dumps(schema_doc, indent=2, default=str), encoding="utf-8")
    (dest / "playbooks.json").write_text(json.dumps(PLAYBOOKS, indent=2), encoding="utf-8")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "n_rows": bundle["n_rows"],
        "n_cards": bundle["n_cards"],
        "scorer_source": bundle.get("scorer_source"),
        "calibration_note": bundle.get("calibration_note"),
        "scenario_sensitivity_val_only": bundle.get("scenario_sensitivity_val_only"),
        "sample_project_keys": sorted({c["project_key"] for c in samples}),
        "outputs": {
            "cards_jsonl": str(jsonl_path),
            "cards_parquet": str(parquet_path),
            "samples": str(dest / "sample_cards.json"),
        },
    }
    (dest / "scenario_sensitivity.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    if bundle.get("audit") is not None:
        audit_path = dest / f"{split}_card_audit.parquet"
        bundle["audit"].to_parquet(audit_path, index=False)
        summary["outputs"]["audit"] = str(audit_path)
        summary["note"] = "val_card_audit.parquet has y_true for the team only. It is not part of the GPT contract."
        (dest / "scenario_sensitivity.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary["outputs"]
