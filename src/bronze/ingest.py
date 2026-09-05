"""Load and persist the source registry; ingest intake files into Bronze (immutable copies)."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.common.paths import (
    BRONZE_DIR,
    REGISTRY_PARQUET,
    REGISTRY_YAML,
    ensure_layer_dirs,
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_registry_yaml(path: Path = REGISTRY_YAML) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("sources", [])


def count_rows_for_source(path: Path, sheet_mode: str) -> int:
    if sheet_mode == "miso_csv":
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace")) - 1
    if sheet_mode == "berkeley_2020_split":
        total = 0
        for sheet in ("active", "withdrawn", "completed"):
            df = pd.read_excel(path, sheet_name=sheet)
            total += len(df)
        return total
    if sheet_mode == "berkeley_data":
        return len(pd.read_excel(path, sheet_name="data"))
    if sheet_mode == "berkeley_lbnl_complete":
        return len(pd.read_excel(path, sheet_name="03. Complete Queue Data", header=1))
    return -1


def ingest_all(repo_root: Path | None = None, overwrite: bool = False) -> pd.DataFrame:
    """
    Copy intake files into data/bronze/{berkeley|miso}/ and write source_registry.parquet.
    Never modifies existing Bronze files in place; overwrite replaces the copy only when requested.
    """
    ensure_layer_dirs()
    sources = load_registry_yaml()
    rows = []
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for src in sources:
        intake = (repo_root or Path(".")) / src["intake_relative_path"]
        if not intake.exists():
            raise FileNotFoundError(f"Intake file missing: {intake}")

        bronze_dir = BRONZE_DIR / src["bronze_subdir"]
        bronze_dir.mkdir(parents=True, exist_ok=True)
        dest = bronze_dir / src["source_file"]

        digest = file_sha256(intake)
        if dest.exists():
            existing = file_sha256(dest)
            if existing != digest:
                if not overwrite:
                    raise RuntimeError(
                        f"Bronze file exists with different hash (never edit Bronze silently): {dest}"
                    )
                shutil.copy2(intake, dest)
            # else: identical, leave untouched
        else:
            shutil.copy2(intake, dest)

        # Verify bronze hash matches intake
        bronze_hash = file_sha256(dest)
        if bronze_hash != digest:
            raise RuntimeError(f"Bronze hash mismatch after copy: {dest}")

        try:
            row_count = count_rows_for_source(dest, src["sheet_mode"])
        except Exception:  # noqa: BLE001
            row_count = None

        rows.append(
            {
                "source_id": src["source_id"],
                "source_name": src["source_name"],
                "source_file": src["source_file"],
                "edition_year": src["edition_year"],
                "data_as_of_date": src["data_as_of_date"],
                "published_at": src["published_at"],
                "retrieved_at": src.get("retrieved_at") or retrieved_at,
                "source_url": src.get("source_url"),
                "file_hash": bronze_hash,
                "row_count": row_count,
                "schema_version": "1.0",
                "bronze_path": str(dest.relative_to(dest.parents[2])),
                "sheet_mode": src["sheet_mode"],
                "project_id_col": src.get("project_id_col"),
                "region_filter_col": src.get("region_filter_col"),
                "region_filter_value": src.get("region_filter_value"),
                "intake_relative_path": src["intake_relative_path"],
                "bronze_subdir": src["bronze_subdir"],
            }
        )

    registry = pd.DataFrame(rows)
    registry.to_parquet(REGISTRY_PARQUET, index=False)
    return registry


def load_registry_parquet() -> pd.DataFrame:
    if not REGISTRY_PARQUET.exists():
        raise FileNotFoundError("Run ingest first to create data/source_registry.parquet")
    return pd.read_parquet(REGISTRY_PARQUET)


if __name__ == "__main__":
    from src.common.paths import REPO_ROOT

    df = ingest_all(REPO_ROOT)
    print(df[["source_id", "file_hash", "row_count"]].to_string(index=False))
