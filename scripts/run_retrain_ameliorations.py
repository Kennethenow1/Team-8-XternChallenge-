#!/usr/bin/env python3
"""Val-only retrain ameliorations (test sealed).

  python scripts/run_retrain_ameliorations.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.retrain_ameliorations import run_retrain_ameliorations


def main() -> int:
    payload = run_retrain_ameliorations()
    print(json.dumps({"promote_candidates": payload.get("promote_candidates"), "test_sealed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
