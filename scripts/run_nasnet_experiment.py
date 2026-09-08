#!/usr/bin/env python3
"""Run NASNetLarge tabular-to-image experiment (TRAIN/VAL only).

  python scripts/run_nasnet_experiment.py
  python scripts/run_nasnet_experiment.py --smoke
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Must configure NVIDIA lib path before TensorFlow import
from src.models.nasnet.train_nasnetlarge import configure_nvidia_lib_path

configure_nvidia_lib_path()

from src.models.nasnet.run_nasnet_experiment import main


if __name__ == "__main__":
    raise SystemExit(main())
