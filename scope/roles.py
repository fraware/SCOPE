"""Reviewer role validation."""

from __future__ import annotations

from typing import Any

from scope.errors import DecisionValidationError, RoleValidationError
from scope.policy import PolicyStore


def validate_role(role: str, policy: PolicyStore) -> None:
    if role not in policy.reviewer_roles:
        raise RoleValidationError(f"Unknown reviewer role: {role}")


def validate_reviewer_for_action(
    role: str,
    action_type: str,
    policy: PolicyStore,
    *,
    required_roles: list[str] | None = None,
    domain_overlay: str | None = None,
) -> None:
    validate_role(role, policy)
    roles = required_roles if required_roles is not None else policy.get_required_roles(
        action_type, domain_overlay=domain_overlay
    )
    if role not in roles:
        raise RoleValidationError(
            f"Reviewer role '{role}' is not authorized for action type '{action_type}'. "
            f"Required: {roles}"
        )


def validate_reviewer_for_scope(
    role: str,
    scope: str,
    policy: PolicyStore,
    *,
    session_mode: bool = False,
) -> None:
    validate_role(role, policy)
    if not policy.role_can_approve_scope(role, scope):
        raise RoleValidationError(
            f"Reviewer role '{role}' cannot approve scope '{scope}'"
        )
    extra_roles = policy.scope_requires_roles(scope)
    if extra_roles and not session_mode:
        raise DecisionValidationError(
            f"Scope '{scope}' requires multi-reviewer session with roles {extra_roles}. "
            "Use 'scope review session' to collect votes from all required roles."
        )


def validate_single_decision_allowed(
    action_type: str,
    policy: PolicyStore,
    *,
    domain_overlay: str | None = None,
) -> None:
    if policy.requires_multi_reviewer_session(action_type, domain_overlay=domain_overlay):
        raise DecisionValidationError(
            f"Action type '{action_type}' requires a multi-reviewer review session. "
            "Single-decision co_reviewers are not supported; use 'scope review session'."
        )


def reviewer_info(reviewer: dict[str, Any], policy: PolicyStore) -> dict[str, Any]:
    role = reviewer["role"]
    validate_role(role, policy)
    info = {
        "reviewer_id": reviewer.get("reviewer_id", "unknown"),
        "role": role,
        "declared_expertise": reviewer.get("declared_expertise", []),
        "conflict_declared": bool(reviewer.get("conflict_declared", False)),
    }
    if reviewer.get("reviewer_public_key_ref"):
        info["reviewer_public_key_ref"] = reviewer["reviewer_public_key_ref"]
    return info
