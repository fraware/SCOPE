"""SCOPE runtime configuration."""

from __future__ import annotations

import os


def is_production_mode() -> bool:
    """Return True when unsigned artifacts must be rejected."""
    value = os.environ.get("SCOPE_PRODUCTION_MODE", "").lower()
    return value in ("1", "true", "yes", "production")


def require_signatures() -> bool:
    return is_production_mode()


def allow_dev_ial0() -> bool:
    """Explicit dev override for caller-supplied identity in production mode."""
    value = os.environ.get("SCOPE_ALLOW_DEV_IAL0", "").lower()
    return value in ("1", "true", "yes")


def review_route_promotion_enabled() -> bool:
    """When true, promote valid review_route values to requested_scope."""
    value = os.environ.get("SCOPE_REVIEW_ROUTE_PROMOTION", "true").lower()
    return value not in ("0", "false", "no")


def api_key() -> str | None:
    """Optional bearer token for REST API authentication."""
    return os.environ.get("SCOPE_API_KEY")
