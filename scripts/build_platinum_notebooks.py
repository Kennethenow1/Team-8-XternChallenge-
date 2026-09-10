#!/usr/bin/env python3
"""Write platinum/*.ipynb — one notebook per delay model. Source of truth for cell text."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "platinum"

RULES = r"""
# {title}

Locked for every platinum notebook:

| Rule | Value |
|------|--------|
| Task | Predict `cod_slip_months_next_12m` (headline **MAE**). Companion: `cod_slip_ge_12m`. |
| Train | 2020–2022 labeled rows |
| Val (selection) | 2023 |
| Test | **sealed** — do not load `*_test.parquet` |
| Split shuffle / SMOTE | **No** |
| PCA on trees | **No** |
| NASNet | GPU only; 100 frozen + 20 finetune; never a 2-epoch smoke |
| Temporal CNN | MAX_EPOCHS=100, MIN_EPOCHS_BEFORE_STOP=8 |

Follow-up window is **24 months** because Berkeley 2024 vintages have empty service dates.
MISO `operational_date` is Appl In Service Date, not proven COD.

```text
CPU:  .\.venv\Scripts\Activate.ps1  then jupyter
GPU:  .\scripts\wsl-python.cmd -m jupyter notebook platinum/{filename}
```

Matrix: `{matrix}`. Trainer: `{trainer}`.
"""

SETUP = r"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from IPython.display import display

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path.cwd().resolve()
for p in [REPO, *REPO.parents]:
    if (p / "src" / "modeling").exists():
        REPO = p
        break
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

MODEL_ID = "__MODEL_ID__"
RESULTS = REPO / "platinum" / "results" / MODEL_ID
(RESULTS / "models").mkdir(parents=True, exist_ok=True)
(RESULTS / "plots").mkdir(parents=True, exist_ok=True)


def probe_cuda() -> dict:
    report: dict = {}
    try:
        import torch
        report["torch"] = torch.__version__
        report["torch_cuda"] = bool(torch.cuda.is_available())
        report["torch_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception as e:  # noqa: BLE001
        report["torch"] = f"unavailable: {e}"
        report["torch_cuda"] = False
        report["torch_device"] = "cpu"
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices("GPU")
        report["tf"] = tf.__version__
        report["tf_gpus"] = [g.name for g in gpus]
        if MODEL_ID != "nasnet_cnn" and gpus:
            try:
                tf.config.set_visible_devices([], "GPU")
                report["tf_gpu_hidden_for_torch"] = True
            except Exception as e:  # noqa: BLE001
                report["tf_gpu_hidden_for_torch"] = f"failed: {e}"
    except Exception as e:  # noqa: BLE001
        report["tf"] = f"unavailable: {e}"
        report["tf_gpus"] = []
    print(json.dumps(report, indent=2))
    return report


CUDA = probe_cuda()
"""

SAVE_HELPERS = r"""
def _public_metrics(m: dict) -> dict:
    skip = {"history", "folds"}
    out = {}
    for k, v in m.items():
        if str(k).startswith("_") or k in skip:
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v)
        elif isinstance(v, (float, int, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, dict) and k == "baselines":
            out[k] = {bk: {kk: float(vv) if isinstance(vv, (int, float, np.floating)) else vv for kk, vv in (bv.items() if isinstance(bv, dict) else [])} if isinstance(bv, dict) else bv for bk, bv in v.items()}
        elif isinstance(v, (list, tuple)) and len(v) <= 80:
            out[k] = list(v)
    return out


def history_frame(m: dict) -> pd.DataFrame:
    hist = m.get("history") or m.get("_history") or []
    if not hist:
        return pd.DataFrame(columns=["step", "train_loss", "val_loss", "train_mae", "val_mae", "val_rmse"])
    return pd.DataFrame(hist)


def _safe_show(fig) -> None:
    try:
        fig.show()
    except Exception as e:  # noqa: BLE001
        print("plotly show skipped:", e)


def plot_pred_vs_actual(m: dict, y=None, pred=None):
    fig = go.Figure()
    mae = m.get("mae")
    fig.add_annotation(text=f"val MAE={mae}", xref="paper", yref="paper", x=0.02, y=0.98, showarrow=False)
    fig.update_layout(title="Val predicted vs actual COD slip (months); 45° = no error", xaxis_title="actual", yaxis_title="predicted")
    try:
        fig.write_html(RESULTS / "plots" / "val_pred_vs_actual.html")
    except Exception as e:  # noqa: BLE001
        print("scatter html skipped:", e)
    _safe_show(fig)
    return fig


def plot_history(df: pd.DataFrame):
    if df.empty:
        print("No epoch/iteration history (single-fit family).")
        return None
    fig = go.Figure()
    for col, name in (("train_loss", "train loss"), ("val_loss", "val loss"), ("train_mae", "train MAE"), ("val_mae", "val MAE")):
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.get("step"), y=df[col], mode="lines", name=name))
    fig.update_layout(title="Train/val curves (headline is MAE, not accuracy)", xaxis_title="step")
    try:
        fig.write_html(RESULTS / "plots" / "history.html")
    except Exception as e:  # noqa: BLE001
        print("history html skipped:", e)
    _safe_show(fig)
    return fig


def append_leaderboard(m: dict) -> None:
    path = REPO / "platinum" / "results" / "leaderboard.csv"
    row = {
        "model": MODEL_ID,
        "run_name": m.get("model", MODEL_ID),
        "split": "val",
        "status": m.get("status"),
        "mae": m.get("mae"),
        "rmse": m.get("rmse"),
        "median_ae": m.get("median_ae"),
        "pinball80": m.get("pinball80"),
        "companion_pr_auc": m.get("companion_pr_auc"),
        "delayed_mw_capture_at_10pct": m.get("delayed_mw_capture_at_10pct"),
        "beats_persist_mae": m.get("beats_persist_mae"),
        "n_features": m.get("n_features"),
        "reason": m.get("reason"),
    }
    df = pd.DataFrame([row])
    if path.exists() and path.stat().st_size > 0:
        old = pd.read_csv(path)
        old = old[old["model"] != MODEL_ID]
        df = pd.concat([old, df], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print("leaderboard →", path)


def save_bundle(m: dict, model_obj=None, model_filename: str = "model.joblib") -> None:
    m = m or {"model": MODEL_ID, "status": "skipped", "reason": "no metrics dict"}
    pub = _public_metrics(m)
    pub.setdefault("model", m.get("model", MODEL_ID))
    pub.setdefault("status", m.get("status", "ok"))
    (RESULTS / "metrics.json").write_text(json.dumps(pub, indent=2, default=str), encoding="utf-8")
    hist = history_frame(m)
    hist.to_csv(RESULTS / "history.csv", index=False)
    if model_obj is not None and str(pub.get("status")) == "ok":
        try:
            import joblib
            joblib.dump(model_obj, RESULTS / "models" / model_filename)
        except Exception as e:  # noqa: BLE001
            print("model save skipped:", e)
    try:
        plot_pred_vs_actual(m)
    except Exception as e:  # noqa: BLE001
        print("scatter skipped:", e)
    try:
        plot_history(hist)
    except Exception as e:  # noqa: BLE001
        print("history plot skipped:", e)
    append_leaderboard(pub)
    print("status=", pub.get("status"), "mae=", pub.get("mae"), "wrote", RESULTS)


def skipped(reason: str) -> dict:
    return {"model": MODEL_ID, "status": "skipped", "reason": str(reason), "split": "val"}
"""


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def write_nb(filename: str, cells: list) -> None:
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    path = OUT / filename
    path.write_text(nbf.writes(nb), encoding="utf-8")
    print("wrote", path)


def base_cells(title: str, filename: str, model_id: str, matrix: str, trainer: str, knobs: str) -> list:
    return [
        md(RULES.format(title=title, filename=filename, matrix=matrix, trainer=trainer)),
        md("## Setup"),
        code(SETUP.replace("__MODEL_ID__", model_id)),
        md("## Knobs"),
        code(knobs.strip()),
        code(SAVE_HELPERS.strip()),
    ]


def train_save(train_src: str) -> list:
    return [
        md("## Load + train (val only)"),
        code(train_src.strip()),
        md("## Val metrics + save"),
        code("save_bundle(metrics, model_obj=metrics.get('_model') if isinstance(metrics, dict) else None)"),
    ]


def build_all() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    lb = OUT / "results" / "leaderboard.csv"
    if not lb.exists():
        lb.write_text(
            "model,run_name,split,status,mae,rmse,median_ae,pinball80,companion_pr_auc,"
            "delayed_mw_capture_at_10pct,beats_persist_mae,n_features,reason\n",
            encoding="utf-8",
        )

    specs = [
        (
            "01_logistic.ipynb",
            "01 — Ridge / ElasticNet delay months",
            "logistic",
            "delay_logistic_v1",
            "src/modeling/delay/train_ridge.py",
            """
KNOBS = {"SEED": 42, "ALPHA": 1.0, "L1_RATIO": 0.0, "ROTATION": "none"}
print(KNOBS)
""",
            """
from src.modeling.delay.train_ridge import fit_ridge_eval
try:
    metrics = fit_ridge_eval(alpha=float(KNOBS["ALPHA"]), l1_ratio=float(KNOBS["L1_RATIO"]), seed=int(KNOBS["SEED"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "rmse", "pinball80", "reason")})
""",
        ),
        (
            "02_catboost.ipynb",
            "02 — CatBoost MAE",
            "catboost",
            "delay_catboost_native_v1",
            "src/modeling/delay/train_catboost.py",
            """
KNOBS = {"SEED": 42, "TASK_TYPE": "CPU", "DROP_SPARSE": False}
print(KNOBS)
""",
            """
from src.modeling.delay.train_catboost import CATBOOST_DELAY_DEFAULT, fit_catboost_delay
try:
    metrics = fit_catboost_delay(seed=int(KNOBS["SEED"]), task_type=KNOBS["TASK_TYPE"])
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "best_iteration", "reason")})
""",
        ),
        (
            "03_lightgbm.ipynb",
            "03 — LightGBM MAE",
            "lightgbm",
            "delay_tree_v1",
            "src/modeling/delay/train_lightgbm.py",
            """
KNOBS = {"SEED": 42}
print(KNOBS)
""",
            """
from src.modeling.delay.train_lightgbm import fit_lightgbm_delay
try:
    metrics = fit_lightgbm_delay(seed=int(KNOBS["SEED"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "best_iteration", "reason")})
""",
        ),
        (
            "04_xgboost.ipynb",
            "04 — XGBoost MAE",
            "xgboost",
            "delay_tree_v1",
            "src/modeling/delay/train_xgboost.py",
            """
KNOBS = {"SEED": 42}
print(KNOBS)
""",
            """
from src.modeling.delay.train_xgboost import fit_xgboost_delay
try:
    metrics = fit_xgboost_delay(seed=int(KNOBS["SEED"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "best_iteration", "reason")})
""",
        ),
        (
            "05_tabm.ipynb",
            "05 — TabM regressor",
            "tabm",
            "delay_tabm_v1",
            "src/modeling/delay/train_tabm.py",
            """
KNOBS = {"SEED": 42, "USE_GPU": True, "MAX_EPOCHS": 200}
print(KNOBS)
""",
            """
from src.modeling.delay.train_tabm import fit_tabm_delay
try:
    metrics = fit_tabm_delay(seed=int(KNOBS["SEED"]), use_gpu=bool(KNOBS["USE_GPU"]), max_epochs=int(KNOBS["MAX_EPOCHS"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "device", "reason")})
""",
        ),
        (
            "06_ft_transformer.ipynb",
            "06 — FT-Transformer Huber",
            "ft_transformer",
            "delay_ftt_v1",
            "src/modeling/delay/train_ft_transformer.py",
            """
KNOBS = {"SEED": 42, "USE_GPU": True, "MAX_EPOCHS": 200}
print(KNOBS)
""",
            """
from src.modeling.delay.train_ft_transformer import fit_ft_transformer_delay
try:
    metrics = fit_ft_transformer_delay(seed=int(KNOBS["SEED"]), use_gpu=bool(KNOBS["USE_GPU"]), max_epochs=int(KNOBS["MAX_EPOCHS"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "device", "reason")})
""",
        ),
        (
            "07_tabicl.ipynb",
            "07 — TabICL companion → delay",
            "tabicl",
            "delay_foundation_v1",
            "src/modeling/delay/train_tabicl.py",
            """
KNOBS = {"SEED": 42, "N_ESTIMATORS": 8}
print(KNOBS)
""",
            """
from src.modeling.delay.train_tabicl import fit_tabicl_delay
try:
    metrics = fit_tabicl_delay(n_estimators=int(KNOBS["N_ESTIMATORS"]), seed=int(KNOBS["SEED"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "reason")})
""",
        ),
        (
            "08_tabpfn.ipynb",
            "08 — TabPFN regressor",
            "tabpfn",
            "delay_foundation_v1",
            "src/modeling/delay/train_tabpfn.py",
            """
KNOBS = {"SEED": 42, "N_ESTIMATORS": 8}
print(KNOBS)
""",
            """
from src.modeling.delay.train_tabpfn import fit_tabpfn_delay
try:
    metrics = fit_tabpfn_delay(n_estimators=int(KNOBS["N_ESTIMATORS"]), seed=int(KNOBS["SEED"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "reason")})
""",
        ),
        (
            "09_seq_cnn.ipynb",
            "09 — Temporal 1D CNN (main CNN)",
            "seq_cnn",
            "delay_seq_v1",
            "src/modeling/delay/train_seq_cnn.py",
            """
KNOBS = {
    "SEED": 42,
    "MAX_EPOCHS": 100,
    "MIN_EPOCHS_BEFORE_STOP": 8,
    "PATIENCE": 15,
    "LR": 1e-3,
    "FILTERS1": 32,
    "FILTERS2": 64,
    "KERNEL": 3,
    "DROPOUT": 0.2,
    "HUBER_DELTA": 12.0,
    "USE_GRU": False,
}
print(KNOBS)
""",
            """
from src.modeling.delay.train_seq_cnn import fit_seq_cnn_delay
try:
    metrics = fit_seq_cnn_delay(
        seed=int(KNOBS["SEED"]),
        max_epochs=int(KNOBS["MAX_EPOCHS"]),
        patience=int(KNOBS["PATIENCE"]),
        lr=float(KNOBS["LR"]),
        filters1=int(KNOBS["FILTERS1"]),
        filters2=int(KNOBS["FILTERS2"]),
        kernel=int(KNOBS["KERNEL"]),
        dropout=float(KNOBS["DROPOUT"]),
        huber_delta=float(KNOBS["HUBER_DELTA"]),
        use_gru=bool(KNOBS["USE_GRU"]),
        min_epochs=int(KNOBS["MIN_EPOCHS_BEFORE_STOP"]),
    )
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "n_epochs", "reason")})
""",
        ),
        (
            "10_nasnet_cnn.ipynb",
            "10 — NASNetLarge delay head (full GPU budget)",
            "nasnet_cnn",
            "delay_logistic_v1",
            "src/modeling/delay/train_nasnet.py",
            """
KNOBS = {"SEED": 42, "DO_FINETUNE": True}
print(KNOBS)
print("NASNet delay uses configs/nasnet_delay.yaml: frozen_epochs=100, finetune=20, require_gpu=true. No MAX_EPOCHS=2 override.")
""",
            """
from src.modeling.delay.train_nasnet import fit_nasnet_delay
try:
    metrics = fit_nasnet_delay(seed=int(KNOBS["SEED"]), do_finetune=bool(KNOBS["DO_FINETUNE"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "n_frozen_epochs", "reason")})
""",
        ),
        (
            "11_survival.ipynb",
            "11 — Survival time-to-COD",
            "survival",
            "survival_cod_training",
            "src/modeling/delay/train_survival.py",
            """
KNOBS = {"VARIANT": "aft_lgbm"}  # aft_lgbm | discrete_logistic
print(KNOBS)
""",
            """
from src.modeling.delay.train_survival import fit_survival_delay
try:
    metrics = fit_survival_delay(variant=str(KNOBS["VARIANT"]))
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "mae", "reason")})
""",
        ),
        (
            "12_timesfm.ipynb",
            "12 — TimesFM system delay series",
            "timesfm",
            "cod_delay_panel monthly",
            "src/modeling/delay/train_timesfm.py",
            """
KNOBS = {"ENGINE": "timesfm"}
print(KNOBS)
""",
            """
from src.modeling.delay.train_timesfm import fit_timesfm_delay
try:
    metrics = fit_timesfm_delay()
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
print({k: metrics.get(k) for k in ("status", "rmse", "mape", "n_folds", "reason")})
""",
        ),
    ]

    for filename, title, model_id, matrix, trainer, knobs, train in specs:
        cells = base_cells(title, filename, model_id, matrix, trainer, knobs)
        cells += train_save(train)
        write_nb(filename, cells)


if __name__ == "__main__":
    build_all()
