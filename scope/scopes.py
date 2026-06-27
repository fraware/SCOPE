"""Approval scope hierarchy and validation."""

from __future__ import annotations

from scope.errors import ScopeValidationError
from scope.policy import PolicyStore


def scope_rank(scope: str, policy: PolicyStore) -> int:
    hierarchy = policy.scope_hierarchy
    if scope not in hierarchy:
        raise ScopeValidationError(f"Unknown approval scope: {scope}")
    return hierarchy.index(scope)


def is_weaker_or_equal(scope_a: str, scope_b: str, policy: PolicyStore) -> bool:
    """Return True if scope_a is weaker than or equal to scope_b."""
    return scope_rank(scope_a, policy) <= scope_rank(scope_b, policy)


def is_stronger(scope_a: str, scope_b: str, policy: PolicyStore) -> bool:
    return scope_rank(scope_a, policy) > scope_rank(scope_b, policy)


def validate_scope(scope: str, policy: PolicyStore) -> None:
    if scope not in policy.scope_hierarchy:
        raise ScopeValidationError(f"Unknown approval scope: {scope}")


def validate_approval_not_overbroad(
    approved_scope: str,
    requested_scope: str | None,
    packet_requested_tool: str | None,
    policy: PolicyStore,
) -> None:
    validate_scope(approved_scope, policy)
    if requested_scope:
        validate_scope(requested_scope, policy)
        if is_stronger(approved_scope, requested_scope, policy):
            raise ScopeValidationError(
                f"Approved scope '{approved_scope}' is stronger than requested '{requested_scope}'"
            )


def resolve_requested_scope_from_tool(tool: str, policy: PolicyStore) -> str | None:
    """Infer the strongest scope that would permit a tool (for overbreadth checks)."""
    best: str | None = None
    best_rank = -1
    for scope_name, scope_def in policy.scope_tools.items():
        allowed = scope_def.get("allowed_tools", [])
        if tool in allowed or "*" in allowed:
            rank = scope_rank(scope_name, policy)
            if rank > best_rank:
                best = scope_name
                best_rank = rank
    return best


def allowed_tools_for_scope(scope: str, policy: PolicyStore) -> list[str]:
    return list(policy.get_scope_tools(scope).get("allowed_tools", []))


def blocked_tools_for_scope(scope: str, policy: PolicyStore) -> list[str]:
    return list(policy.get_scope_tools(scope).get("blocked_tools", []))
