#!/usr/bin/env python3
"""Execute the PIT withdrawal EDA notebook and export HTML under reports/eda/."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NB = REPO / "notebooks" / "eda_pit_withdrawal.ipynb"
OUT_HTML = REPO / "reports" / "eda" / "eda_report.html"
FIG_DIR = REPO / "reports" / "eda" / "figures"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Do not regenerate notebook from builder")
    parser.add_argument("--timeout", type=int, default=600, help="Per-cell execute timeout seconds")
    args = parser.parse_args()

    py = REPO / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    if not args.skip_build:
        subprocess.check_call([str(py), str(REPO / "scripts" / "build_eda_notebook.py")], cwd=REPO)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)

    # Execute in place so figures land under reports/eda/figures
    subprocess.check_call(
        [
            str(py),
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            f"--ExecutePreprocessor.timeout={args.timeout}",
            "--ExecutePreprocessor.kernel_name=python3",
            str(NB),
        ],
        cwd=REPO,
    )

    subprocess.check_call(
        [
            str(py),
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "html",
            "--output",
            OUT_HTML.name,
            "--output-dir",
            str(OUT_HTML.parent),
            str(NB),
        ],
        cwd=REPO,
    )

    print(f"Notebook: {NB}")
    print(f"HTML:     {OUT_HTML}")
    print(f"Figures:  {FIG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
