"""NASNetLarge tabular-to-image experiment (TRAIN/VAL only; TEST/SCORE sealed)."""

from __future__ import annotations

from pathlib import Path

from src.common.paths import GOLD_DIR, REPO_ROOT

NASNET_DATA_DIR = GOLD_DIR / "modeling" / "nasnet"
NASNET_ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "nasnet"
NASNET_REPORTS_DIR = REPO_ROOT / "reports" / "models" / "nasnet"

MODEL_READY_TRAIN = GOLD_DIR / "modeling" / "model_ready_train.parquet"
MODEL_READY_VAL = GOLD_DIR / "modeling" / "model_ready_val.parquet"

SEALED_BASENAMES = frozenset(
    {
        "model_ready_test.parquet",
        "model_ready_score.parquet",
        "model_ready_test.csv",
        "model_ready_score.csv",
    }
)

TARGET_CANDIDATES = (
    "withdraw_next_12m",
    "withdrawn_next_12_months",
    "withdrawn_next_12m",
)

META_EXCLUDE = frozenset(
    {
        "project_key",
        "observation_date",
        "split",
        "target",
        "withdrawal_date",
        "final_status",
        "withdraw_next_12m",
        "withdrawn_next_12_months",
        "withdrawn_next_12m",
        "next_outcome",
        "complete_followup",
        "outcome_type",
        "outcome_date",
    }
)

FEATURE_ROLES_X = frozenset({"numeric", "binary", "onehot", "missing_indicator"})


def ensure_nasnet_dirs() -> None:
    for p in (NASNET_DATA_DIR, NASNET_ARTIFACTS_DIR, NASNET_REPORTS_DIR):
        p.mkdir(parents=True, exist_ok=True)


def assert_not_sealed_path(path: Path) -> None:
    name = path.name.lower()
    if name in SEALED_BASENAMES or "model_ready_test" in name or "model_ready_score" in name:
        raise RuntimeError(
            f"Refusing to read sealed split path during NASNet development: {path}. "
            "TEST/SCORE stay sealed until explicit approval."
        )
