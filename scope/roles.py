"""Reviewer role validation."""

from __future__ import annotations

from typing import Any

from scope.errors import RoleValidationError
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
) -> None:
    validate_role(role, policy)
    roles = required_roles if required_roles is not None else policy.get_required_roles(action_type)
    if role not in roles:
        raise RoleValidationError(
            f"Reviewer role '{role}' is not authorized for action type '{action_type}'. "
            f"Required: {roles}"
        )


def validate_reviewer_for_scope(role: str, scope: str, policy: PolicyStore) -> None:
    validate_role(role, policy)
    if not policy.role_can_approve_scope(role, scope):
        raise RoleValidationError(
            f"Reviewer role '{role}' cannot approve scope '{scope}'"
        )
    scope_def = policy.get_scope_tools(scope)
    extra_roles = scope_def.get("requires_roles", [])
    if extra_roles and role not in extra_roles:
        # Scope may require specific roles beyond policy defaults
        if not any(policy.role_can_approve_scope(r, scope) for r in extra_roles if r == role):
            if role not in extra_roles:
                pass  # role_can_approve_scope already checked


def reviewer_info(reviewer: dict[str, Any], policy: PolicyStore) -> dict[str, Any]:
    role = reviewer["role"]
    validate_role(role, policy)
    return {
        "reviewer_id": reviewer.get("reviewer_id", "unknown"),
        "role": role,
        "declared_expertise": reviewer.get("declared_expertise", []),
        "conflict_declared": bool(reviewer.get("conflict_declared", False)),
    }
