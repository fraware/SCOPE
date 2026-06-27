"""Grant expiration checking."""

from __future__ import annotations

from typing import Any

from scope.errors import ExpirationError


def check_expiration(
    grant: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    used: bool = False,
) -> None:
    """Raise ExpirationError if grant is expired under context."""
    context = context or {}
    expiration = grant.get("expiration", {})
    constraints = grant.get("constraints", {})
    triggers = expiration.get("expires_after", [])

    if "single_use" in triggers and used:
        raise ExpirationError("Grant expired: single_use consumed")

    if constraints.get("single_use") and context.get("grant_used"):
        raise ExpirationError("Grant expired: single_use constraint violated")

    if "protocol_version_change" in triggers:
        grant_version = constraints.get("protocol_version")
        ctx_version = context.get("protocol_version")
        if grant_version and ctx_version and grant_version != ctx_version:
            raise ExpirationError(
                f"Grant expired: protocol version changed ({grant_version} -> {ctx_version})"
            )

    if "evidence_state_change" in triggers:
        grant_state = context.get("grant_evidence_state") or constraints.get("evidence_state")
        ctx_state = context.get("evidence_state")
        if grant_state and ctx_state and grant_state != ctx_state:
            raise ExpirationError(
                f"Grant expired: evidence state changed ({grant_state} -> {ctx_state})"
            )

    if "validation_status_change" in triggers:
        grant_val = constraints.get("validation_status")
        ctx_val = context.get("validation_status")
        if grant_val and ctx_val and grant_val != ctx_val:
            raise ExpirationError("Grant expired: validation status changed")

    if "policy_version_change" in triggers:
        grant_policy = grant.get("provenance", {}).get("scope_policy_version")
        ctx_policy = context.get("scope_policy_version")
        if grant_policy and ctx_policy and grant_policy != ctx_policy:
            raise ExpirationError("Grant expired: policy version changed")

    if context.get("revoked"):
        raise ExpirationError("Grant expired: manually revoked")

    if context.get("safety_incident") and "safety_incident" in triggers:
        raise ExpirationError("Grant expired: safety incident")

    absolute = expiration.get("absolute_expiration")
    if absolute and context.get("current_time"):
        if context["current_time"] >= absolute:
            raise ExpirationError("Grant expired: absolute expiration reached")


def is_expired(
    grant: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    used: bool = False,
) -> bool:
    try:
        check_expiration(grant, context, used=used)
        return False
    except ExpirationError:
        return True
