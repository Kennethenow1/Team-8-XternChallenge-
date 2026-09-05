"""Resolve Berkeley ↔ MISO project identities into a project_crosswalk."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.common.paths import SILVER_DIR, ensure_layer_dirs


def _norm_id(x: str | None) -> str | None:
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    s = str(x).strip().upper()
    s = re.sub(r"\s+", "", s)
    return s or None


def _cap_sim(a, b) -> float:
    if pd.isna(a) or pd.isna(b):
        return 0.0
    a, b = float(a), float(b)
    if a == 0 and b == 0:
        return 1.0
    denom = max(abs(a), abs(b), 1.0)
    return max(0.0, 1.0 - abs(a - b) / denom)


def _poi_sim(a, b) -> float:
    if not a or not b or pd.isna(a) or pd.isna(b):
        return 0.0
    return 1.0 if str(a) == str(b) else 0.0


def match_score(row_b: pd.Series, row_m: pd.Series, id_match: bool) -> float:
    s = 0.50 * float(id_match)
    if pd.notna(row_b.get("queue_date")) and pd.notna(row_m.get("queue_date")):
        if pd.Timestamp(row_b["queue_date"]).normalize() == pd.Timestamp(row_m["queue_date"]).normalize():
            s += 0.15
    if row_b.get("state_code") and row_m.get("state_code") and row_b["state_code"] == row_m["state_code"]:
        s += 0.10
    if (
        row_b.get("technology_primary")
        and row_m.get("technology_primary")
        and row_b["technology_primary"] == row_m["technology_primary"]
    ):
        s += 0.10
    s += 0.10 * _cap_sim(row_b.get("capacity_mw"), row_m.get("capacity_mw"))
    s += 0.05 * _poi_sim(row_b.get("poi_key"), row_m.get("poi_key"))
    return round(s, 4)


def build_crosswalk() -> pd.DataFrame:
    ensure_layer_dirs()
    berkeley = pd.read_parquet(SILVER_DIR / "projects" / "berkeley_all.parquet")
    miso = pd.read_parquet(SILVER_DIR / "projects" / "miso_all.parquet")

    # Use latest Berkeley observation per source_project_id for matching attributes
    berkeley = berkeley.sort_values("observation_date")
    b_latest = berkeley.groupby("source_project_id", as_index=False).tail(1).copy()
    b_latest["norm_id"] = b_latest["source_project_id"].map(_norm_id)
    miso = miso.copy()
    miso["norm_id"] = miso["source_project_id"].map(_norm_id)

    b_by_id = {k: r for k, r in b_latest.set_index("norm_id").iterrows() if k}
    m_by_id = {k: r for k, r in miso.set_index("norm_id").iterrows() if k}

    rows = []
    matched_b = set()
    matched_m = set()

    # 1) Exact normalized queue ID
    for nid in sorted(set(b_by_id) & set(m_by_id)):
        rb, rm = b_by_id[nid], m_by_id[nid]
        score = match_score(rb, rm, id_match=True)
        # Validate with queue date / state / tech when available — still accept exact ID
        review = "accepted"
        method = "exact_normalized_queue_id"
        # Flag weak attribute support for review but keep match
        if score < 0.65:
            review = "accepted_weak_attrs"
        rows.append(
            {
                "project_key": f"P::{nid}",
                "berkeley_project_id": rb["source_project_id"],
                "miso_project_id": rm["source_project_id"],
                "match_method": method,
                "match_confidence": score,
                "review_status": review,
                "berkeley_capacity_mw": rb.get("capacity_mw"),
                "miso_capacity_mw": rm.get("capacity_mw"),
            }
        )
        matched_b.add(nid)
        matched_m.add(nid)

    # Berkeley-only
    for nid, rb in b_by_id.items():
        if nid in matched_b:
            continue
        rows.append(
            {
                "project_key": f"P::B::{rb['source_project_id']}",
                "berkeley_project_id": rb["source_project_id"],
                "miso_project_id": None,
                "match_method": "berkeley_only",
                "match_confidence": 1.0,
                "review_status": "accepted",
                "berkeley_capacity_mw": rb.get("capacity_mw"),
                "miso_capacity_mw": None,
            }
        )

    # MISO-only — do not auto fuzzy-match; leave for manual review queue
    # Optional: generate needs_review candidates by queue_date+state+capacity (not auto-accepted)
    unmatched_m = [m_by_id[nid] for nid in m_by_id if nid not in matched_m]
    unmatched_b = [b_by_id[nid] for nid in b_by_id if nid not in matched_b]

    # Candidate approximate matches for review only
    for rm in unmatched_m:
        best = None
        best_score = 0.0
        for rb in unmatched_b:
            # Require same state_code to even consider
            if rb.get("state_code") and rm.get("state_code") and rb["state_code"] != rm["state_code"]:
                continue
            sc = match_score(rb, rm, id_match=False)
            if sc > best_score:
                best_score = sc
                best = rb
        if best is not None and best_score >= 0.35:
            rows.append(
                {
                    "project_key": f"P::CAND::{rm['source_project_id']}",
                    "berkeley_project_id": best["source_project_id"],
                    "miso_project_id": rm["source_project_id"],
                    "match_method": "approximate_candidate",
                    "match_confidence": best_score,
                    "review_status": "needs_review",
                    "berkeley_capacity_mw": best.get("capacity_mw"),
                    "miso_capacity_mw": rm.get("capacity_mw"),
                }
            )
        rows.append(
            {
                "project_key": f"P::M::{rm['source_project_id']}",
                "berkeley_project_id": None,
                "miso_project_id": rm["source_project_id"],
                "match_method": "miso_only",
                "match_confidence": 1.0,
                "review_status": "accepted",
                "berkeley_capacity_mw": None,
                "miso_capacity_mw": rm.get("capacity_mw"),
            }
        )

    cross = pd.DataFrame(rows)
    cross["capacity_difference_mw"] = pd.to_numeric(cross["berkeley_capacity_mw"], errors="coerce") - pd.to_numeric(
        cross["miso_capacity_mw"], errors="coerce"
    )
    cross["capacity_conflict_flag"] = (
        cross["berkeley_capacity_mw"].notna()
        & cross["miso_capacity_mw"].notna()
        & (cross["capacity_difference_mw"].abs() > 5)
    )

    # Keep accepted identity rows for key assignment; candidates are extra review rows
    out_path = SILVER_DIR / "crosswalks" / "project_crosswalk.parquet"
    cross.to_parquet(out_path, index=False)
    cross.to_csv(SILVER_DIR / "crosswalks" / "project_crosswalk.csv", index=False)
    print(f"crosswalk rows={len(cross)} accepted={int((cross.review_status.str.startswith('accepted')).sum())}")
    return cross


def apply_project_keys(projects: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Attach stable project_key from accepted crosswalk rows."""
    accepted = crosswalk[crosswalk["review_status"].astype(str).str.startswith("accepted")].copy()
    # Prefer rows that are not candidate placeholders
    accepted = accepted[accepted["match_method"] != "approximate_candidate"]

    b_map = {
        r["berkeley_project_id"]: r["project_key"]
        for _, r in accepted.dropna(subset=["berkeley_project_id"]).iterrows()
    }
    m_map = {
        r["miso_project_id"]: r["project_key"]
        for _, r in accepted.dropna(subset=["miso_project_id"]).iterrows()
    }

    def _key(row):
        if row["source_name"] == "Berkeley":
            return b_map.get(row["source_project_id"], f"P::B::{row['source_project_id']}")
        return m_map.get(row["source_project_id"], f"P::M::{row['source_project_id']}")

    out = projects.copy()
    out["project_key"] = out.apply(_key, axis=1)
    return out


if __name__ == "__main__":
    build_crosswalk()
