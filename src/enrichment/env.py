"""Load enrichment secrets from repo-root .env without printing values."""

from __future__ import annotations

from pathlib import Path

from src.common.paths import REPO_ROOT


def load_enrichment_env() -> None:
    """Load REPO_ROOT/.env into os.environ if present. Never logs secret values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(REPO_ROOT) / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
