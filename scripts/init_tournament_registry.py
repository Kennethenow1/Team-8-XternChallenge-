#!/usr/bin/env python3
"""Initialize tournament registry from existing artifacts.

  python scripts/init_tournament_registry.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.tournament_registry import (
    ALL_RUNS_PATH,
    CHAMPION_PATH,
    GOAL_STATUS_PATH,
    LEADERBOARD_MD,
    ingest_existing_artifacts,
    refresh_leaderboard,
)


def main() -> int:
    # Fresh ingest: remove stale all_runs to avoid duplicates on re-run
    if ALL_RUNS_PATH.exists():
        ALL_RUNS_PATH.unlink()
    counts = ingest_existing_artifacts()
    refresh_leaderboard()
    print(json.dumps({
        "ingested": counts,
        "all_runs": str(ALL_RUNS_PATH),
        "leaderboard": str(LEADERBOARD_MD),
        "champion": str(CHAMPION_PATH),
        "goal_status": str(GOAL_STATUS_PATH),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
