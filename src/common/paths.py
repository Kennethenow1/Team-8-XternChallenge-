"""Repository path helpers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
QUALITY_DIR = DATA_DIR / "quality_reports"
CONFIGS_DIR = REPO_ROOT / "configs"
INTAKE_DIR = DATA_DIR / "intake"

REGISTRY_YAML = CONFIGS_DIR / "source_registry.yaml"
REGISTRY_PARQUET = DATA_DIR / "source_registry.parquet"

STATUS_MAP_YAML = REPO_ROOT / "src" / "common" / "status_map.yaml"
TECH_MAP_YAML = REPO_ROOT / "src" / "common" / "technology_map.yaml"


def ensure_layer_dirs() -> None:
    for p in [
        INTAKE_DIR,
        BRONZE_DIR / "berkeley",
        BRONZE_DIR / "miso",
        SILVER_DIR / "projects",
        SILVER_DIR / "snapshots",
        SILVER_DIR / "outcomes",
        SILVER_DIR / "crosswalks",
        SILVER_DIR / "external",
        GOLD_DIR / "annual_withdrawal_training",
        GOLD_DIR / "survival_training",
        GOLD_DIR / "current_miso_scoring",
        QUALITY_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)
