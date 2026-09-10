"""Load the freeze / Electrum CatBoost scorer. Does not unseal test. Does not promote a new champion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.paths import REPO_ROOT
from src.modeling.foundation_matrix import NATIVE_CATEGORICALS
from src.modeling.model_registry import ARTIFACTS_DIR, load_xy
from src.modeling.train_catboost import CATBOOST_TRIAL_149

PLATT_PATH = ARTIFACTS_DIR / "calibration" / "catboost_tuned" / "platt" / "calibrator.joblib"
ELECTRUM_MODEL = REPO_ROOT / "electrum" / "results" / "catboost" / "models" / "model.cbm.joblib"
FREEZE_CANDIDATES = (
    ARTIFACTS_DIR / "models" / "catboost_tuned" / "model.cbm.joblib",
    ARTIFACTS_DIR / "models" / "catboost_tuned" / "model.joblib",
    ARTIFACTS_DIR / "models" / "catboost_tuned" / "model.cbm",
)


def _prep_cats(X: pd.DataFrame) -> pd.DataFrame:
    out = X.copy()
    for c in NATIVE_CATEGORICALS:
        if c in out.columns:
            out[c] = out[c].astype("string").fillna("__MISSING__")
    return out


def _apply_platt(calibrator, y_prob: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(y_prob, dtype=float), 1e-7, 1.0 - 1e-7)
    logit = np.log(p / (1.0 - p)).reshape(-1, 1)
    return calibrator.predict_proba(logit)[:, 1]


def _align(X: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    missing = [c for c in feature_names if c not in X.columns]
    if missing:
        raise RuntimeError(f"scorer features missing from matrix: {missing[:12]}")
    return X.loc[:, feature_names]


class QuitScorer:
    def __init__(
        self,
        model: Any,
        *,
        source: str,
        feature_names: list[str],
        calibrator: Any | None = None,
        calibration_note: str | None = None,
    ) -> None:
        self.model = model
        self.source = source
        self.feature_names = list(feature_names)
        self.calibrator = calibrator
        self.calibration_note = calibration_note

    def predict_raw(self, X: pd.DataFrame) -> np.ndarray:
        Xp = _align(_prep_cats(X), self.feature_names)
        return np.asarray(self.model.predict_proba(Xp)[:, 1], dtype=float)

    def predict(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
        raw = self.predict_raw(X)
        if self.calibrator is None:
            return raw, None
        return raw, _apply_platt(self.calibrator, raw)


def _load_joblib(path: Path):
    import joblib

    return joblib.load(path)


def resolve_scorer(*, fit_if_missing: bool = True) -> QuitScorer:
    for path in FREEZE_CANDIDATES:
        if path.exists():
            model = _load_joblib(path) if path.suffix != ".cbm" else _load_cbm(path)
            names = list(getattr(model, "feature_names_", []))
            cal = _load_joblib(PLATT_PATH) if PLATT_PATH.exists() else None
            note = "Platt on catboost_tuned (freeze). Raw for rank; Platt for P(quit)." if cal is not None else "Freeze model; Platt artifact missing — raw only."
            return QuitScorer(model, source="catboost_tuned", feature_names=names, calibrator=cal, calibration_note=note)

    if ELECTRUM_MODEL.exists():
        model = _load_joblib(ELECTRUM_MODEL)
        names = list(getattr(model, "feature_names_", []))
        return QuitScorer(
            model,
            source="electrum_catboost",
            feature_names=names,
            calibrator=None,
            calibration_note=(
                "Electrum CatBoost joblib (trial-149 recipe). Freeze catboost_tuned is not on disk "
                "(gitignored). Do not apply freeze Platt to this score distribution."
            ),
        )

    if not fit_if_missing:
        raise FileNotFoundError("No freeze or Electrum CatBoost model found")

    return _fit_trial149_cpu()


def _load_cbm(path: Path):
    from catboost import CatBoostClassifier

    m = CatBoostClassifier()
    m.load_model(path)
    return m


def _fit_trial149_cpu() -> QuitScorer:
    from src.modeling.train_catboost import fit_catboost_eval

    params = {**CATBOOST_TRIAL_149, "task_type": "CPU"}
    m = fit_catboost_eval(params=params, save=False, model_name="platinum3_scorer")
    if m.get("status") != "ok":
        raise RuntimeError(f"platinum3 scorer fit failed: {m}")
    model = m["_model"]
    names = list(m.get("_feature_list", {}).get("feature_columns") or getattr(model, "feature_names_", []))
    return QuitScorer(
        model,
        source="trial149_refit_cpu",
        feature_names=names,
        calibrator=None,
        calibration_note="Refit trial-149 on train (CPU) because freeze/Electrum models were missing. Not a new champion.",
    )


def load_split_xy(split: str, matrix_prefix: str = "catboost_native_v1"):
    if split == "test":
        raise RuntimeError("Split 'test' is sealed. Platinum 3 will not score test rows.")
    return load_xy(matrix_prefix, split)
