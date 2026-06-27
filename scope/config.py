"""SCOPE runtime configuration."""

from __future__ import annotations

import os


def is_production_mode() -> bool:
    """Return True when unsigned artifacts must be rejected."""
    value = os.environ.get("SCOPE_PRODUCTION_MODE", "").lower()
    return value in ("1", "true", "yes", "production")


def require_signatures() -> bool:
    return is_production_mode()
