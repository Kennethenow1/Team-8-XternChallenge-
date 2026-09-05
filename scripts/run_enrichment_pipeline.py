#!/usr/bin/env python3
"""Run enrichment feature-store pipeline (does NOT rebuild Berkeley/MISO core tables)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.enrichment.env import load_enrichment_env

load_enrichment_env()

from src.enrichment.build_crosswalks import build_all_crosswalks
from src.enrichment.build_enriched_gold import build_enriched_panels
from src.enrichment.populate import populate_all
from src.enrichment.registry import ensure_enrichment_dirs
from src.enrichment.reports import build_all_reports
from src.enrichment.skeletons import write_all_skeleton_tables


def main() -> int:
    ensure_enrichment_dirs()

    print("=== E0/E2: Write typed Silver skeletons (missing only) ===")
    write_all_skeleton_tables(only_if_missing=True)

    print("\n=== E0: Geo / developer / EIA crosswalks ===")
    build_all_crosswalks()

    print("\n=== E1: Populate open + queue-derived sources ===")
    populate_all(run_deferred_county_joins=True)

    print("\n=== E2: Re-assert empty skeletons for tables still empty ===")
    # Never overwrite populated tables (esp. miso_dpp_events).
    write_all_skeleton_tables(only_if_missing=True)

    print("\n=== E3: Enriched Gold panels ===")
    result = build_enriched_panels()

    print("\n=== E3: Manifests / coverage / dictionary ===")
    build_all_reports(result["annual"])

    # Deprecate note for old external stubs
    dep = REPO_ROOT / "data" / "silver" / "external" / "DEPRECATED.txt"
    dep.write_text(
        "Superseded by data/silver/enrichment/. Kept for backward reference only.\n",
        encoding="utf-8",
    )

    print("\nEnrichment pipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
