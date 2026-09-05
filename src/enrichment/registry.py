"""Enrichment registry, Bronze paths, and mandatory Silver metadata."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.common.paths import CONFIGS_DIR, DATA_DIR, REPO_ROOT, ensure_layer_dirs

ENRICHMENT_REGISTRY_YAML = CONFIGS_DIR / "enrichment_registry.yaml"
BRONZE_ENRICHMENT = DATA_DIR / "bronze" / "enrichment"
SILVER_ENRICHMENT = DATA_DIR / "silver" / "enrichment"
ENRICHMENT_REPORTS = DATA_DIR / "quality_reports" / "enrichment"

MANDATORY_COLUMNS = [
    "effective_date",
    "available_date",
    "source_name",
    "source_url",
    "retrieved_at",
    "entity_key",
    "geographic_key",
    "match_method",
    "match_confidence",
]


def ensure_enrichment_dirs() -> None:
    ensure_layer_dirs()
    BRONZE_ENRICHMENT.mkdir(parents=True, exist_ok=True)
    SILVER_ENRICHMENT.mkdir(parents=True, exist_ok=True)
    ENRICHMENT_REPORTS.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "silver" / "crosswalks").mkdir(parents=True, exist_ok=True)


def load_enrichment_registry(path: Path = ENRICHMENT_REGISTRY_YAML) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("sources", [])


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bronze_dir(source_id: str) -> Path:
    p = BRONZE_ENRICHMENT / source_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_bronze_bytes(source_id: str, filename: str, content: bytes, overwrite: bool = False) -> Path:
    """Write immutable Bronze file; refuse silent hash changes unless overwrite."""
    dest = bronze_dir(source_id) / filename
    digest = hashlib.sha256(content).hexdigest()
    if dest.exists():
        existing = file_sha256(dest)
        if existing != digest and not overwrite:
            raise RuntimeError(f"Bronze exists with different hash: {dest}")
        if existing == digest:
            return dest
    dest.write_bytes(content)
    import json

    meta = dest.with_suffix(dest.suffix + ".meta.json")
    meta.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "filename": filename,
                "file_hash": digest,
                "retrieved_at": utc_now_iso(),
                "bytes": len(content),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return dest


def write_bronze_text(source_id: str, filename: str, text: str, overwrite: bool = False) -> Path:
    return write_bronze_bytes(source_id, filename, text.encode("utf-8"), overwrite=overwrite)


def validate_silver_metadata(df: pd.DataFrame, table_name: str) -> None:
    missing = [c for c in MANDATORY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{table_name} missing mandatory columns: {missing}")


def empty_enrichment_frame(extra_columns: list[str] | None = None) -> pd.DataFrame:
    cols = list(MANDATORY_COLUMNS) + (extra_columns or [])
    return pd.DataFrame({c: pd.Series(dtype="object") for c in cols})


def attach_metadata(
    df: pd.DataFrame,
    *,
    source_name: str,
    source_url: str | None,
    retrieved_at: str | None = None,
    match_method: str = "direct",
    match_confidence: float = 1.0,
    entity_key_col: str | None = None,
    geographic_key_col: str | None = None,
) -> pd.DataFrame:
    out = df.copy()
    out["source_name"] = source_name
    out["source_url"] = source_url
    out["retrieved_at"] = retrieved_at or utc_now_iso()
    out["match_method"] = match_method
    out["match_confidence"] = match_confidence
    if entity_key_col and entity_key_col in out.columns:
        out["entity_key"] = out[entity_key_col].astype(str)
    elif "entity_key" not in out.columns:
        out["entity_key"] = None
    if geographic_key_col and geographic_key_col in out.columns:
        out["geographic_key"] = out[geographic_key_col].astype(str)
    elif "geographic_key" not in out.columns:
        out["geographic_key"] = None
    return out


def write_silver_table(name: str, df: pd.DataFrame) -> Path:
    ensure_enrichment_dirs()
    validate_silver_metadata(df, name)
    path = SILVER_ENRICHMENT / f"{name}.parquet"
    df.to_parquet(path, index=False)
    return path
