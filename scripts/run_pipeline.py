#!/usr/bin/env python3
"""Orchestrate Bronze → Silver → Gold pipeline with DQ gates."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/run_pipeline.py` from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bronze.ingest import ingest_all
from src.bronze.profile_source import profile_all
from src.common.paths import QUALITY_DIR, REPO_ROOT as ROOT, ensure_layer_dirs
from src.gold.build_training import build_all_gold
from src.silver.build_master_snapshots import build_master_and_snapshots
from src.silver.build_outcomes import build_outcomes
from src.silver.crosswalk import build_crosswalk
from src.silver.external_stubs import write_external_stubs
from src.silver.standardize_berkeley import standardize_all_berkeley
from src.silver.standardize_miso import standardize_all_miso


def main() -> int:
    ensure_layer_dirs()
    print("=== 1. Ingest Bronze + source registry ===")
    registry = ingest_all(ROOT)
    print(registry[["source_id", "row_count", "data_as_of_date"]].to_string(index=False))

    print("\n=== 2. Profile sources (join gate) ===")
    profile_all(require_pass=True)
    print("Profile gate:", (QUALITY_DIR / "profile_gate.txt").read_text().strip())

    print("\n=== 3. Standardize Berkeley (MISO only) ===")
    standardize_all_berkeley()

    print("\n=== 4. Standardize MISO ===")
    standardize_all_miso()

    print("\n=== 5. Crosswalk ===")
    build_crosswalk()

    print("\n=== 6. Master + snapshots + deltas ===")
    build_master_and_snapshots()

    print("\n=== 7. Outcomes ===")
    build_outcomes()

    print("\n=== 8. Gold training / scoring ===")
    build_all_gold()

    print("\n=== 9. External stubs ===")
    write_external_stubs()

    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
