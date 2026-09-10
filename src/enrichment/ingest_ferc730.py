"""Best-effort FERC-730 ingest. Skip the transmission model if this is not clean."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    attach_metadata,
    empty_enrichment_frame,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_silver_table,
)

SOURCE_ID = "ferc_730"
# Form 730 is filed in eLibrary; there is no stable bulk CSV. We probe a few
# public index URLs and refuse to invent a delay panel from HTML junk.
CANDIDATE_URLS = [
    "https://www.ferc.gov/industries-data/electric/general-information/electric-industry-forms",
]


def run_ferc730_harvest() -> dict[str, Any]:
    ensure_enrichment_dirs()
    extra = [
        "project_name",
        "transmission_owner",
        "planned_isd",
        "status",
        "on_schedule",
        "delay_reason",
        "delay_months",
    ]
    notes: list[str] = []
    for url in CANDIDATE_URLS:
        try:
            req = Request(url, headers={"User-Agent": "team8-miso-queue/0.1"})
            with urlopen(req, timeout=20) as resp:
                body = resp.read(2000)
            notes.append(f"reached {url} bytes={len(body)} (no project-level table)")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"failed {url}: {exc}")

    empty = empty_enrichment_frame(extra)
    empty = attach_metadata(
        empty,
        source_name="FERC Form 730",
        source_url=CANDIDATE_URLS[0],
        match_method="none",
        match_confidence=0.0,
    )
    write_silver_table("ferc730_projects", empty)
    summary = {
        "status": "skipped_not_clean",
        "n": 0,
        "note": (
            "FERC-730 is not available as a clean bulk table. Transmission delay "
            "modeling is skipped. Use NERC LTRA (110 of 1,160 projects delayed) "
            "and MTEP nearby counts as supporting context."
        ),
        "inventory": notes,
        "retrieved_at": utc_now_iso(),
    }
    (ENRICHMENT_REPORTS / "ferc730_harvest_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("ferc730 skipped (no clean bulk table)")
    return summary


if __name__ == "__main__":
    run_ferc730_harvest()
