#!/usr/bin/env python3
"""Write electrum/*.ipynb (one notebook per model; duplicated setup, no electrum/lib.py)."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "electrum"

RULES = r"""
# {title}

Locked for every electrum notebook:

| Rule | Value |
|------|--------|
| Train | 2020–2022 |
| Val (selection) | 2023 |
| Test | **sealed** — do not load `*_test.parquet` |
| Split shuffle | **No** (calendar splits only) |
| 50/50 resampling / SMOTE | **No** |
| PCA on trees | **No** |
| Headline score | **PR-AUC** (val chance ≈ 0.041; Strong ≥ 0.10) |
| Accuracy | Logged on train/val curves only — a bad headline here (always-stay wins) |

CUDA on this Windows machine is **WSL2**, not native PowerShell. Trees: CPU. TabM / FT-T: torch CUDA if available. NASNet: TF GPU via WSL; warn instead of a silent CPU marathon.

```text
CPU:  .\.venv\Scripts\Activate.ps1  then jupyter
GPU:  .\scripts\wsl-python.cmd -m jupyter notebook electrum/{filename}
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
RESULTS = REPO / "electrum" / "results" / MODEL_ID
(RESULTS / "models").mkdir(parents=True, exist_ok=True)
(RESULTS / "plots").mkdir(parents=True, exist_ok=True)

CHANCE_PR = 0.041
STRONG_PR = 0.10


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
        report["tf_built_with_cuda"] = bool(tf.test.is_built_with_cuda())
        # Keep TF from grabbing the whole card so later torch training can use CUDA.
        # NASNet re-enables TF GPU in its train cell via require_gpu().
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
    if not report.get("torch_cuda") and not report.get("tf_gpus"):
        print("No CUDA visible in this kernel. Trees are fine on CPU. For TabM/FT-T/NASNet use WSL: scripts/wsl-python.cmd")
    return report


CUDA = probe_cuda()
"""

SAVE_HELPERS = r"""
def _public_metrics(m: dict) -> dict:
    skip = {"history"}
    out = {}
    for k, v in m.items():
        if str(k).startswith("_") or k in skip:
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v)
        elif isinstance(v, (float, int, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)) and len(v) <= 50:
            out[k] = list(v)
    return out


def history_frame(m: dict) -> pd.DataFrame:
    hist = m.get("history") or m.get("_history") or []
    if not hist:
        return pd.DataFrame(columns=["step", "train_loss", "train_acc", "val_loss", "val_acc", "val_pr_auc"])
    return pd.DataFrame(hist)


def _safe_show(fig) -> None:
    try:
        fig.show()
    except Exception as e:  # noqa: BLE001
        print("plotly show skipped (headless):", e)


def plot_metrics_bar(m: dict):
    raw = m.get("pr_auc")
    pr = float(raw) if raw is not None and raw == raw else float("nan")
    fig = go.Figure(
        data=[
            go.Bar(name="this run", x=["PR-AUC"], y=[pr]),
            go.Bar(name="chance 0.041", x=["PR-AUC"], y=[CHANCE_PR]),
            go.Bar(name="Strong 0.10", x=["PR-AUC"], y=[STRONG_PR]),
        ]
    )
    fig.update_layout(title="Val PR-AUC vs chance / Strong (test sealed)", barmode="group", yaxis_title="PR-AUC")
    try:
        fig.write_html(RESULTS / "plots" / "val_pr_auc.html")
    except Exception as e:  # noqa: BLE001
        print("pr-auc html skipped:", e)
    _safe_show(fig)
    return fig


def plot_history(df: pd.DataFrame):
    if df.empty:
        print("No epoch/iteration history (single-fit family). metrics.json still written.")
        return None
    fig = go.Figure()
    for col, name in (
        ("train_loss", "train loss"),
        ("val_loss", "val loss"),
        ("train_acc", "train acc"),
        ("val_acc", "val acc"),
    ):
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.get("step", df.get("epoch")), y=df[col], mode="lines", name=name))
    fig.update_layout(
        title="Train/val loss and accuracy (accuracy is not the headline; PR-AUC is)",
        xaxis_title="step (iteration ≈ epoch)",
        yaxis_title="value",
    )
    try:
        fig.write_html(RESULTS / "plots" / "history.html")
    except Exception as e:  # noqa: BLE001
        print("history html skipped:", e)
    _safe_show(fig)
    return fig


def append_leaderboard(m: dict) -> None:
    path = REPO / "electrum" / "results" / "leaderboard.csv"
    row = {
        "model": MODEL_ID,
        "run_name": m.get("model", MODEL_ID),
        "split": "val",
        "status": m.get("status"),
        "pr_auc": m.get("pr_auc"),
        "pr_lift": m.get("pr_lift"),
        "roc_auc": m.get("roc_auc"),
        "log_loss": m.get("log_loss"),
        "brier": m.get("brier"),
        "precision_at_10pct": m.get("precision_at_10pct"),
        "withdrawn_mw_capture_at_10pct": m.get("withdrawn_mw_capture_at_10pct"),
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
            print("model →", RESULTS / "models" / model_filename)
        except Exception as e:  # noqa: BLE001
            print("model save skipped:", e)
    try:
        plot_metrics_bar(m)
    except Exception as e:  # noqa: BLE001
        print("metrics bar skipped:", e)
    try:
        plot_history(hist)
    except Exception as e:  # noqa: BLE001
        print("history plot skipped:", e)
    append_leaderboard(pub)
    print("status=", pub.get("status"), "wrote", RESULTS)


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


def build_all() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    lb = OUT / "results" / "leaderboard.csv"
    if not lb.exists():
        lb.write_text(
            "model,run_name,split,status,pr_auc,pr_lift,roc_auc,log_loss,brier,"
            "precision_at_10pct,withdrawn_mw_capture_at_10pct,n_features,reason\n",
            encoding="utf-8",
        )

    # --- 01 logistic ---
    cells = base_cells(
        "01 — Logistic / elastic-net",
        "01_logistic.ipynb",
        "logistic",
        "logistic_v1",
        "src/modeling/train_logistic.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,  # optional loss reweight — not 50/50 rows
    "PENALTY": "l2",            # "l2" or "elasticnet"
    "C": 1.0,
    "L1_RATIO": 0.5,
    "ROTATION": "none",         # "none" | "pls" | "pca" (PCA is a negative control)
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train (val only)"),
        code(
            """
from src.modeling.retrain_ameliorations import fit_logistic_rotation
from src.modeling.train_logistic import fit_logistic_eval

model_obj = None
try:
    rot = str(KNOBS.get("ROTATION", "none")).lower()
    if rot in {"pls", "pca"}:
        metrics = fit_logistic_rotation(mode=rot)
        print("rotation", rot, "— sklearn pipeline not dumped as a single joblib")
    elif KNOBS["PENALTY"] == "elasticnet":
        metrics = fit_logistic_eval(
            name="logistic_elasticnet",
            penalty="elasticnet",
            C=float(KNOBS["C"]),
            l1_ratio=float(KNOBS["L1_RATIO"]),
            save=False,
        )
        model_obj = metrics.get("_model")
    else:
        metrics = fit_logistic_eval(name="logistic_l2", penalty="l2", C=float(KNOBS["C"]), save=False)
        model_obj = metrics.get("_model")
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "pr_auc", "roc_auc", "log_loss", "withdrawn_mw_capture_at_10pct", "reason")})
"""
        ),
        md("## Val metrics + save"),
        code("save_bundle(metrics, model_obj=model_obj, model_filename='model.joblib')"),
    ]
    write_nb("01_logistic.ipynb", cells)

    # --- 02 catboost ---
    cells = base_cells(
        "02 — CatBoost (reference / ship path)",
        "02_catboost.ipynb",
        "catboost",
        "catboost_native_v1",
        "src/modeling/train_catboost.py (trial-149 params)",
        """
KNOBS = {
    "SEED": 2026,                 # deploy seed; also try 42 / 123 then average in a later cell if you want the bag
    "USE_CLASS_WEIGHT": False,    # CatBoost auto_class_weights=Balanced
    "DROP_SPARSE": False,         # ablation — do not auto-drop
    "DROP_NEWS_DRIFT": False,     # drop news*; do NOT auto-drop FRED/EIA macros
    "MW_SAMPLE_WEIGHT": False,    # sample_weight ∝ capacity_mw
    "MONOTONE": False,
    "FOCAL": False,               # dump if it only flags everyone
    "TASK_TYPE": "CPU",           # GPU if CatBoost CUDA is actually available
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.retrain_ameliorations import MONO_UP, NEWS_DRIFT_COLS, SPARSE_CANDIDATES
from src.modeling.train_catboost import CATBOOST_TRIAL_149, fit_catboost_eval

try:
    params = {**CATBOOST_TRIAL_149, "random_seed": int(KNOBS["SEED"]), "task_type": KNOBS["TASK_TYPE"]}
    if str(params.get("task_type", "")).upper() == "CPU":
        params.pop("devices", None)
    if KNOBS["USE_CLASS_WEIGHT"]:
        params["auto_class_weights"] = "Balanced"
    if KNOBS["FOCAL"]:
        params["loss_function"] = "Focal:focal_alpha=0.25;focal_gamma=2.0"

    drop = []
    if KNOBS["DROP_SPARSE"]:
        drop += SPARSE_CANDIDATES
    if KNOBS["DROP_NEWS_DRIFT"]:
        drop += NEWS_DRIFT_COLS
    mono = {c: 1 for c in MONO_UP} if KNOBS["MONOTONE"] else None

    metrics = fit_catboost_eval(
        params=params,
        drop_cols=drop or None,
        sample_weight_from="capacity_mw" if KNOBS["MW_SAMPLE_WEIGHT"] else None,
        monotone_constraints=mono,
        model_name="catboost_electrum",
        save=False,
    )
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "pr_auc", "roc_auc", "log_loss", "withdrawn_mw_capture_at_10pct", "best_iteration", "dump", "reason")})
"""
        ),
        md("## Val metrics, curves, save"),
        code(
            """
model_obj = metrics.get("_model")
# native CatBoost dump alongside joblib
if model_obj is not None:
    try:
        model_obj.save_model(str(RESULTS / "models" / "model.cbm"))
    except Exception as e:
        print("cbm save skipped", e)
save_bundle(metrics, model_obj=model_obj, model_filename="model.cbm.joblib")
"""
        ),
    ]
    write_nb("02_catboost.ipynb", cells)

    # --- 03 lightgbm ---
    cells = base_cells(
        "03 — LightGBM (log-loss focus)",
        "03_lightgbm.ipynb",
        "lightgbm",
        "tree_v1",
        "src/modeling/train_lightgbm.py",
        """
from src.modeling.retrain_ameliorations import LGBM_LOGLOSS_FOCUS

KNOBS = {
    "SEED": 2026,
    "USE_CLASS_WEIGHT": False,  # scale_pos_weight ~ train 88/12 ≈ 7
    "DROP_SPARSE": False,
    "LOGLOSS_FOCUS": True,      # stronger L2 / shallower trees vs default HPO PR-AUC peak
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.retrain_ameliorations import SPARSE_CANDIDATES
from src.modeling.train_lightgbm import fit_lightgbm_eval

try:
    params = dict(LGBM_LOGLOSS_FOCUS) if KNOBS["LOGLOSS_FOCUS"] else {}
    params["random_state"] = int(KNOBS["SEED"])
    if KNOBS["USE_CLASS_WEIGHT"]:
        params["scale_pos_weight"] = 7.0
    drop = SPARSE_CANDIDATES if KNOBS["DROP_SPARSE"] else None
    metrics = fit_lightgbm_eval(params=params, drop_cols=drop, model_name="lightgbm_electrum", save=False)
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "pr_auc", "roc_auc", "log_loss", "withdrawn_mw_capture_at_10pct", "best_iteration", "reason")})
"""
        ),
        md("## Val metrics, curves, save"),
        code("save_bundle(metrics, model_obj=metrics.get('_model'), model_filename='model.joblib')"),
    ]
    write_nb("03_lightgbm.ipynb", cells)

    # --- 04 xgboost ---
    cells = base_cells(
        "04 — XGBoost (log-loss focus)",
        "04_xgboost.ipynb",
        "xgboost",
        "tree_v1",
        "src/modeling/train_xgboost.py",
        """
from src.modeling.retrain_ameliorations import XGB_LOGLOSS_FOCUS

KNOBS = {
    "SEED": 2026,
    "USE_CLASS_WEIGHT": False,
    "DROP_SPARSE": False,
    "LOGLOSS_FOCUS": True,
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.retrain_ameliorations import SPARSE_CANDIDATES
from src.modeling.train_xgboost import fit_xgboost_eval

try:
    params = dict(XGB_LOGLOSS_FOCUS) if KNOBS["LOGLOSS_FOCUS"] else {}
    params["random_state"] = int(KNOBS["SEED"])
    if KNOBS["USE_CLASS_WEIGHT"]:
        params["scale_pos_weight"] = 7.0
    drop = SPARSE_CANDIDATES if KNOBS["DROP_SPARSE"] else None
    metrics = fit_xgboost_eval(params=params, drop_cols=drop, model_name="xgboost_electrum", save=False)
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "pr_auc", "roc_auc", "log_loss", "withdrawn_mw_capture_at_10pct", "best_iteration", "reason")})
"""
        ),
        md("## Val metrics, curves, save"),
        code("save_bundle(metrics, model_obj=metrics.get('_model'), model_filename='model.joblib')"),
    ]
    write_nb("04_xgboost.ipynb", cells)

    # --- 05 tabm ---
    cells = base_cells(
        "05 — TabM",
        "05_tabm.ipynb",
        "tabm",
        "tabm_v1",
        "src/modeling/train_tabm.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,  # TabM uses cross-entropy on natural mix
    "DROP_SPARSE": False,
    "USE_GPU": True,
    "MAX_EPOCHS": 200,
    "USE_PLS": False,           # low-priority; numeric PLS is implemented for logistic (01)
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.retrain_ameliorations import SPARSE_CANDIDATES
from src.modeling.train_tabm import fit_tabm_eval

try:
    if KNOBS["USE_PLS"]:
        print("TabM PLS is low-priority and not wired into fit_tabm_eval; run 01_logistic with ROTATION='pls' instead.")
    params = {
        "seed": int(KNOBS["SEED"]),
        "use_gpu": bool(KNOBS["USE_GPU"]) and bool(CUDA.get("torch_cuda")),
        "max_epochs": int(KNOBS["MAX_EPOCHS"]),
    }
    drop = SPARSE_CANDIDATES if KNOBS["DROP_SPARSE"] else None
    metrics = fit_tabm_eval(params=params, drop_cols=drop, model_name="tabm_electrum", save=False)
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss", "device", "best_epoch")})
"""
        ),
        md("## Val metrics, curves, save"),
        code(
            """
obj = metrics.get("_model")
save_bundle(metrics, model_obj=obj, model_filename="model.tabm.pt.joblib")
"""
        ),
    ]
    write_nb("05_tabm.ipynb", cells)

    # --- 06 ft-transformer ---
    cells = base_cells(
        "06 — FT-Transformer",
        "06_ft_transformer.ipynb",
        "ft_transformer",
        "ftt_v1",
        "src/modeling/train_ft_transformer.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": True,   # trainer already uses pos_weight = n_neg/n_pos; this knob keeps that default
    "USE_GPU": True,
    "MAX_EPOCHS": 200,
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.train_ft_transformer import fit_ft_transformer_eval

try:
    params = {
        "seed": int(KNOBS["SEED"]),
        "use_gpu": bool(KNOBS["USE_GPU"]) and bool(CUDA.get("torch_cuda")),
        "max_epochs": int(KNOBS["MAX_EPOCHS"]),
    }
    metrics = fit_ft_transformer_eval(params=params, model_name="ft_transformer_electrum", save=False)
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss", "device", "best_epoch")})
print("history rows", len(metrics.get("history") or metrics.get("_history") or []))
"""
        ),
        md("## Val metrics, curves, save"),
        code("save_bundle(metrics, model_obj=metrics.get('_params'), model_filename='model.ftt.meta.joblib')"),
    ]
    write_nb("06_ft_transformer.ipynb", cells)

    # --- 07 tabicl ---
    cells = base_cells(
        "07 — TabICL",
        "07_tabicl.ipynb",
        "tabicl",
        "foundation_v1",
        "src/modeling/train_tabicl.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.train_tabicl import train_tabicl_default

try:
    metrics = train_tabicl_default()
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss")})
"""
        ),
        md("## Val metrics + save (no epoch loop)"),
        code("save_bundle(metrics, model_obj=None, model_filename='model.joblib')"),
    ]
    write_nb("07_tabicl.ipynb", cells)

    # --- 08 tabpfn ---
    cells = base_cells(
        "08 — TabPFN",
        "08_tabpfn.ipynb",
        "tabpfn",
        "foundation_v1",
        "src/modeling/train_tabpfn.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,
}
print(KNOBS)
print("Needs TABPFN_TOKEN in repo-root .env if the library requires it.")
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.train_tabpfn import train_tabpfn_default

try:
    metrics = train_tabpfn_default()
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss")})
if CUDA.get("torch_cuda"):
    print("torch CUDA is visible; TabPFN will use it if the library supports it.")
"""
        ),
        md("## Val metrics + save (no epoch loop)"),
        code("save_bundle(metrics, model_obj=None, model_filename='model.joblib')"),
    ]
    write_nb("08_tabpfn.ipynb", cells)

    # --- 09 nasnet ---
    cells = base_cells(
        "09 — NASNetLarge CNN",
        "09_nasnet_cnn.ipynb",
        "nasnet_cnn",
        "NASNet ready tensors under data/gold/modeling/nasnet",
        "src/models/nasnet/train_nasnetlarge.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": True,   # NASNet trainer already uses balanced class_weight
    "RUN_TRAIN": False,         # auto-flipped True below if this kernel has a TF GPU
    "MAX_EPOCHS": 2,            # short GPU rerun; never a CPU marathon
}
if CUDA.get("tf_gpus"):
    KNOBS["RUN_TRAIN"] = True
    print("TF GPU visible → RUN_TRAIN=True (MAX_EPOCHS=2)")
else:
    print("No TF GPU → reload/skip; will not train NASNetLarge on CPU")
print(KNOBS)
""",
    )
    cells += [
        md(
            """
## CUDA warning

NASNetLarge on CPU is an all-day job. This notebook **refuses** a silent CPU run.
The prior experiment is **closed** (`experiment_status: closed`). Default `RUN_TRAIN=False` reloads existing metrics.
On WSL with a visible TF GPU, set `RUN_TRAIN=True` for a clean (budget-limited) rerun.
"""
        ),
        code(
            """
from pathlib import Path
import json as _json

from src.models.nasnet import NASNET_ARTIFACTS_DIR, NASNET_REPORTS_DIR
from src.models.nasnet.train_nasnetlarge import require_gpu, train_frozen_and_finetune


def _reload_closed_history(reason: str) -> dict:
    out = {"model": "nasnet_cnn", "status": "skipped", "reason": reason, "split": "val"}
    for cand in (
        NASNET_REPORTS_DIR / "nasnet_experiment.md",
        Path("reports/models/nasnet/nasnet_experiment.md"),
    ):
        p = cand if cand.is_absolute() else REPO / cand
        if p.exists():
            print("existing report:", p)
            break
    hist_json = NASNET_ARTIFACTS_DIR / "history_frozen_seed_42.json"
    if hist_json.exists():
        raw = _json.loads(hist_json.read_text(encoding="utf-8"))
        n = max(len(v) for v in raw.values()) if raw else 0
        hist = []
        for i in range(n):
            hist.append({
                "step": float(i),
                "train_loss": float(raw.get("loss", [float("nan")])[i]) if i < len(raw.get("loss", [])) else float("nan"),
                "train_acc": float(raw.get("accuracy", raw.get("acc", [float("nan")]))[i]) if i < len(raw.get("accuracy", raw.get("acc", []))) else float("nan"),
                "val_loss": float(raw.get("val_loss", [float("nan")])[i]) if i < len(raw.get("val_loss", [])) else float("nan"),
                "val_acc": float(raw.get("val_accuracy", raw.get("val_acc", [float("nan")]))[i]) if i < len(raw.get("val_accuracy", raw.get("val_acc", []))) else float("nan"),
                "val_pr_auc": float(raw.get("val_pr_auc", [float("nan")])[i]) if i < len(raw.get("val_pr_auc", [])) else float("nan"),
            })
        out["history"] = hist
        out["status"] = "ok"
        out["reason"] = reason
        print("reloaded", hist_json)
    return out


tf_gpus = CUDA.get("tf_gpus") or []
print("TF GPUs", tf_gpus)
run_train = bool(KNOBS["RUN_TRAIN"]) and bool(tf_gpus)

if not run_train:
    metrics = _reload_closed_history(
        "no TF GPU in this kernel — reloaded closed-experiment history; refused CPU marathon"
        if not tf_gpus
        else "RUN_TRAIN=False — reloaded closed-experiment history"
    )
else:
    try:
        hw = require_gpu(require=True)
        print("hardware", hw)
        from src.models.nasnet.preprocess_nasnet import load_config

        cfg = load_config()
        cfg.setdefault("training", {})
        cfg["training"]["do_finetune"] = False  # MAX_EPOCHS only applies to frozen; do not start a 20-epoch finetune
        out = train_frozen_and_finetune(
            seed=int(KNOBS["SEED"]),
            config=cfg,
            max_epochs_override=int(KNOBS["MAX_EPOCHS"]),
        )
        metrics = dict(out) if isinstance(out, dict) else {"model": "nasnet_cnn", "status": "ok", "raw": str(out)}
        metrics.setdefault("model", "nasnet_cnn")
        metrics.setdefault("status", "ok")
        hist_obj = out.get("history") if isinstance(out, dict) else None
        if hist_obj is not None and hasattr(hist_obj, "history"):
            h = hist_obj.history
            n = max(len(v) for v in h.values()) if h else 0
            metrics["history"] = [
                {
                    "step": float(i),
                    "train_loss": float(h.get("loss", [float("nan")])[i]) if i < len(h.get("loss", [])) else float("nan"),
                    "train_acc": float(h.get("accuracy", h.get("acc", [float("nan")]))[i]) if i < len(h.get("accuracy", h.get("acc", []))) else float("nan"),
                    "val_loss": float(h.get("val_loss", [float("nan")])[i]) if i < len(h.get("val_loss", [])) else float("nan"),
                    "val_acc": float(h.get("val_accuracy", h.get("val_acc", [float("nan")]))[i]) if i < len(h.get("val_accuracy", h.get("val_acc", []))) else float("nan"),
                }
                for i in range(n)
            ]
    except Exception as e:  # noqa: BLE001
        print("NASNet train failed; falling back to reload:", e)
        metrics = _reload_closed_history(f"train failed ({type(e).__name__}: {e}); reloaded closed history")

print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss")})
"""
        ),
        md("## Save"),
        code("save_bundle(metrics, model_obj=None)"),
    ]
    write_nb("09_nasnet_cnn.ipynb", cells)

    # --- 10 survival ---
    cells = base_cells(
        "10 — Survival (discrete logistic + Cox-TV)",
        "10_survival.ipynb",
        "survival",
        "survival_training parquet (aligned to modeling val)",
        "src/modeling/train_survival.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,
    "VARIANT": "discrete_logistic",  # discrete_logistic | cox_tv | boost_lgbm | rsf
}
print(KNOBS)
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.train_survival import (
    fit_boosted_discrete_hazard,
    fit_cox_tv,
    fit_discrete_logistic_hazard,
    fit_random_survival_forest,
)

try:
    fn = {
        "discrete_logistic": fit_discrete_logistic_hazard,
        "cox_tv": fit_cox_tv,
        "boost_lgbm": fit_boosted_discrete_hazard,
        "rsf": fit_random_survival_forest,
    }[KNOBS["VARIANT"]]
    metrics = fn(save=False)
except Exception as e:  # noqa: BLE001
    metrics = skipped(f"{type(e).__name__}: {e}")
    print("TRAIN FAILED (recorded as skip):", metrics["reason"])
print({k: metrics.get(k) for k in ("status", "reason", "pr_auc", "roc_auc", "log_loss", "alignment")})
"""
        ),
        md("## Val metrics + save (no epoch loop for Cox / logistic)"),
        code("save_bundle(metrics, model_obj=None)"),
    ]
    write_nb("10_survival.ipynb", cells)

    # --- 11 timesfm ---
    cells = base_cells(
        "11 — TimesFM (system monthly forecast)",
        "11_timesfm.ipynb",
        "timesfm",
        "system monthly series (not a project-row classifier)",
        "src/modeling/train_timesfm.py",
        """
KNOBS = {
    "SEED": 42,
    "USE_CLASS_WEIGHT": False,
}
print(KNOBS)
print("TimesFM is a system-level forecast. It does not produce project-row PR-AUC; leaderboard will store RMSE/MAPE.")
""",
    )
    cells += [
        md("## Load + train"),
        code(
            """
from src.modeling.train_timesfm import run_timesfm_experiment

try:
    result = run_timesfm_experiment(save=True)
except Exception as e:  # noqa: BLE001
    result = {"models": {}, "folds": [], "n_folds": 0, "error": f"{type(e).__name__}: {e}"}
    print("TimesFM experiment failed; writing skip row:", e)

print("models", list((result.get("models") or {}).keys()))
print({k: result.get("models", {}).get(k) for k in ("naive", "ma3", "arima", "timesfm")})
tfm = (result.get("models") or {}).get("timesfm") or {}
naive = (result.get("models") or {}).get("naive") or {}
metrics = {
    "model": "timesfm",
    "status": "ok" if (tfm or naive) else "skipped",
    "split": "val",
    "pr_auc": None,
    "roc_auc": None,
    "log_loss": None,
    "rmse": (tfm or naive).get("rmse"),
    "mape": (tfm or naive).get("mape"),
    "reason": result.get("error") or "system forecast — not project-row PR-AUC",
    "n_folds": result.get("n_folds"),
}
# optional fold RMSE as a pseudo-history
hist = []
for i, fold in enumerate(result.get("folds") or []):
    preds = (fold.get("preds") or {}).get("timesfm")
    actual = fold.get("actual")
    if preds is None or actual is None:
        continue
    err = abs(float(preds) - float(actual))
    hist.append({"step": float(i), "train_loss": float("nan"), "train_acc": float("nan"), "val_loss": err, "val_acc": float("nan")})
metrics["history"] = hist
"""
        ),
        md("## Save + leaderboard row"),
        code("save_bundle(metrics, model_obj=None)"),
    ]
    write_nb("11_timesfm.ipynb", cells)


if __name__ == "__main__":
    build_all()
