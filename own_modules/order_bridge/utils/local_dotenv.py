# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Load ``/app/.env`` into ``os.environ`` for local development only.

Docker Compose injects ``env_file`` when the container is **created**; this
reloads the file on each Odoo process start so edits take effect after
restarting ``odoo-bin`` (no container recreate).

Skipped when the file is missing (production / Railway) or when Railway env
markers are set. Keys fixed by devcontainer ``environment:`` are never
overridden so local Postgres settings stay intact.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

# docker-compose ``environment:`` wins over ``env_file`` for these keys.
_COMPOSE_PROTECTED_KEYS = frozenset(
    {
        "PGHOST",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "PGPORT",
        "ODOO_DATA_DIR",
        "ODOO_ADDONS_PATH",
    }
)

_RAILWAY_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID")

_DEFAULT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _is_railway_runtime() -> bool:
    return any(os.environ.get(name) for name in _RAILWAY_MARKERS)


def _unquote_value(raw: str) -> str:
    value = raw.strip()
    if len(value) < 2:
        return value
    quote = value[0]
    if quote not in ('"', "'") or value[-1] != quote:
        return value
    inner = value[1:-1]
    if quote == "'":
        return inner
    # Double-quoted: minimal escape handling (Compose / dotenv compatible).
    return (
        inner.replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].strip()
    if "=" not in stripped:
        return None
    key, _, raw_value = stripped.partition("=")
    key = key.strip()
    if not key:
        return None
    return key, _unquote_value(raw_value)


def load_local_dotenv(env_path: Path | None = None) -> int:
    """Load ``.env`` into ``os.environ`` (override). Returns keys loaded."""
    if _is_railway_runtime():
        return 0

    path = env_path if env_path is not None else _DEFAULT_ENV_PATH
    if not path.is_file():
        return 0

    loaded = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        if key in _COMPOSE_PROTECTED_KEYS:
            continue
        os.environ[key] = value
        loaded += 1

    if loaded:
        _logger.info("Loaded %d variable(s) from %s", loaded, path)
    return loaded
