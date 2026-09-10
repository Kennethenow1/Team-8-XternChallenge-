#!/usr/bin/env python3
"""Write platinum2/*.ipynb — one notebook per delayed-MW model."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum2"

RULES = r"""
# {title}

Locked for every platinum2 notebook:

| Rule | Value |
|------|--------|
| Task | Forecast **delayed MW** (EIA planned stock; GIA is an overlay). |
| Headline | 12-month-ahead RMSE vs seasonal naive |
| Sanity | 3-month-ahead RMSE |
| Val | origins whose **target year ≤ 2023** (12m) / 2023 origins for 3m |
| Test | **2024 sealed** |
| Split shuffle | **No** |

This is not Platinum 1 project-row months of slip.

```text
CPU:  .\.venv\Scripts\Activate.ps1
GPU (TimesFM):  wsl … python scripts/run_platinum2_all.py --only timesfm
```

Trainer: `{trainer}`.
"""

SETUP = r"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO = Path.cwd().resolve()
for p in [REPO, *REPO.parents]:
    if (p / "src" / "modeling").exists():
        REPO = p
        break
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODEL_ID = "__MODEL_ID__"
RESULTS = REPO / "platinum2" / "results" / MODEL_ID
(RESULTS / "models").mkdir(parents=True, exist_ok=True)
(RESULTS / "plots").mkdir(parents=True, exist_ok=True)
"""

FIT = r"""
from src.modeling.platinum2.trainers import {trainer}

m = {trainer}()
keys = [k for k in m if k not in ("history", "folds", "_model")]
print(json.dumps({{k: m[k] for k in keys}}, indent=2, default=str))
"""

SAVE = r"""
keys = ("model", "status", "rmse", "mape", "rmse_h3", "mape_h3", "n_folds_h12", "n_folds_h3", "beats_seasonal_naive", "reason")
pub = {{k: m.get(k) for k in keys}}
(RESULTS / "metrics.json").write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")
pd.DataFrame(m.get("history") or []).to_csv(RESULTS / "history.csv", index=False)
print("wrote", RESULTS / "metrics.json")
"""


def cell_md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def cell_code(text: str):
    return nbf.v4.new_code_cell(text.strip())


SPECS = [
    ("01_seasonal_naive.ipynb", "Seasonal naive", "seasonal_naive", "fit_seasonal_naive"),
    ("02_naive.ipynb", "Last-value naive", "naive", "fit_naive"),
    ("03_ma3.ipynb", "Moving average (3)", "ma3", "fit_ma3"),
    ("04_holt.ipynb", "Damped Holt", "holt", "fit_holt"),
    ("05_arima.ipynb", "ARIMA(1,0,1)", "arima", "fit_arima"),
    ("06_ridge_lags.ipynb", "Ridge on lags + last shift", "ridge_lags", "fit_ridge_lags"),
    ("07_timesfm.ipynb", "TimesFM-3 zero-shot", "timesfm", "fit_timesfm"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    (OUT / "results" / ".gitkeep").write_text("", encoding="utf-8")
    for filename, title, model_id, trainer in SPECS:
        nb = nbf.v4.new_notebook()
        nb["cells"] = [
            cell_md(RULES.format(title=title, filename=filename, trainer=trainer)),
            cell_code(SETUP.replace("__MODEL_ID__", model_id)),
            cell_code(FIT.format(trainer=trainer)),
            cell_code(SAVE),
        ]
        nb["metadata"] = {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        }
        (OUT / filename).write_text(nbf.writes(nb), encoding="utf-8")
        print("wrote", OUT / filename)


if __name__ == "__main__":
    main()
