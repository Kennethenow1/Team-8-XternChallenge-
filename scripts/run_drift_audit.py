#!/usr/bin/env python3
"""Write label/followup + train→val feature drift reports.

  python scripts/run_drift_audit.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.modeling.drift_audit import run_all_audits


def main() -> int:
    paths = run_all_audits()
    print(json.dumps(paths, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
