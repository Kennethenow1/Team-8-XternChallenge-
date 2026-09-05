#!/usr/bin/env python3
"""Export key Gold/Silver parquet tables to CSV for Excel / sharing.

Usage (from repo root):
  .venv/bin/python scripts/export_tables_to_csv.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = REPO_ROOT / "data" / "exports" / "csv"

# Relative to repo root — modeling tables + useful silver context
TABLES: list[tuple[str, str]] = [
    ("data/gold/withdrawal_panel_enriched.parquet", "withdrawal_panel_enriched.csv"),
    ("data/gold/current_miso_scoring_enriched.parquet", "current_miso_scoring_enriched.csv"),
    ("data/gold/annual_withdrawal_training", "annual_withdrawal_training.csv"),
    ("data/gold/survival_training", "survival_training.csv"),
    ("data/gold/current_miso_scoring", "current_miso_scoring.csv"),
    ("data/silver/projects/project_master.parquet", "project_master.csv"),
    ("data/silver/snapshots/project_snapshots.parquet", "project_snapshots.csv"),
    ("data/silver/crosswalks/geo_crosswalk.parquet", "geo_crosswalk.csv"),
    ("data/silver/enrichment/market_zone_month.parquet", "market_zone_month.csv"),
]


def _resolve_parquet(path: Path) -> Path | None:
    if path.is_file() and path.suffix == ".parquet":
        return path
    if path.is_dir():
        parts = sorted(path.rglob("*.parquet"))
        return parts[0] if parts else None
    return None


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []

    for rel_in, out_name in TABLES:
        src = _resolve_parquet(REPO_ROOT / rel_in)
        if src is None:
            skipped.append(rel_in)
            continue
        df = pd.read_parquet(src)
        out = OUT_DIR / out_name
        df.to_csv(out, index=False)
        written.append(f"{out_name}  rows={len(df):,}  cols={len(df.columns)}  -> {out.relative_to(REPO_ROOT)}")

    print(f"CSV export directory: {OUT_DIR.relative_to(REPO_ROOT)}")
    for line in written:
        print(f"  wrote {line}")
    for rel in skipped:
        print(f"  skip (missing): {rel}")
    print(f"Done. {len(written)} file(s) written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
