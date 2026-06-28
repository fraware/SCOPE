"""Two-stage institutional authority: org RBAC then SCOPE scope policy."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from scope.errors import RoleValidationError, ScopeValidationError
from scope.identity_assurance import IdentityAssuranceContext, is_institutional_assurance
from scope.policy import PolicyStore
from scope.rbac import check_rbac_permission, resolve_effective_roles_with_provenance
from scope.roles import validate_reviewer_for_action, validate_reviewer_for_scope


def check_institutional_rbac_stage(
    reviewer_id: str,
    role: str,
    action: str,
    policy_dir: str | Path,
    *,
    at: datetime | None = None,
    identity_context: IdentityAssuranceContext | None = None,
) -> None:
    """
    Stage 1: verify reviewer holds effective institutional role (with delegation expiry).

    When identity assurance is below IAL3, institutional RBAC is not enforced unless
    caller explicitly enables RBAC enforcement via environment.
    """
    if identity_context and not identity_context.institutional_authority:
        if not is_institutional_assurance(identity_context.identity_assurance_level):
            return
    role_info = resolve_effective_roles_with_provenance(
        reviewer_id,
        role,
        policy_dir,
        at=at,
    )
    effective = role_info["effective_roles"]
    if role not in effective:
        raise ScopeValidationError(
            f"Institutional RBAC: reviewer {reviewer_id} lacks effective role {role} "
            f"(has {sorted(effective)})"
        )
    if role_info.get("delegation_expired"):
        raise ScopeValidationError(
            f"Institutional RBAC: delegation for role {role} has expired for {reviewer_id}"
        )
    check_rbac_permission(reviewer_id, role, action, policy_dir, at=at)


def check_scope_policy_stage(
    role: str,
    action_type: str,
    policy: PolicyStore,
    *,
    approved_scope: str | None = None,
    required_roles: list[str] | None = None,
    domain_overlay: str | None = None,
    session_mode: bool = False,
) -> None:
    """Stage 2: verify SCOPE reviewer_roles.yaml permits action and scope approval."""
    try:
        validate_reviewer_for_action(
            role,
            action_type,
            policy,
            required_roles=required_roles,
            domain_overlay=domain_overlay,
        )
    except RoleValidationError as exc:
        raise ScopeValidationError(f"SCOPE policy authority: {exc}") from exc

    if approved_scope:
        try:
            validate_reviewer_for_scope(
                role,
                approved_scope,
                policy,
                session_mode=session_mode,
            )
        except (RoleValidationError, ScopeValidationError) as exc:
            raise ScopeValidationError(f"SCOPE scope authority: {exc}") from exc


def enforce_decision_authority(
    reviewer: dict[str, Any],
    packet: dict[str, Any],
    decision_input: dict[str, Any],
    policy: PolicyStore,
    *,
    identity_context: IdentityAssuranceContext | None = None,
    enforce_rbac: bool = False,
    session_mode: bool = False,
    allowed_veto_roles: list[str] | None = None,
    at: datetime | None = None,
) -> None:
    """Run two-stage authority checks before accepting a decision."""
    reviewer_id = str(reviewer.get("reviewer_id", ""))
    role = str(reviewer.get("role", ""))
    action_type = packet["review_request"]["scientific_action_type"]
    domain_overlay = packet.get("scientific_context", {}).get("domain_overlay")
    required_roles = packet["review_request"].get("required_review_roles")
    decision_type = str(decision_input.get("type", ""))

    rbac_action = "vote_in_session" if session_mode else "submit_decisions"
    should_enforce_rbac = enforce_rbac or (
        identity_context is not None and identity_context.institutional_authority
    )
    if should_enforce_rbac:
        check_institutional_rbac_stage(
            reviewer_id,
            role,
            rbac_action,
            policy.policy_dir,
            at=at,
            identity_context=identity_context,
        )

    approved_scope = None
    if policy.is_approval_decision(decision_type):
        approved_scope = decision_input.get("approved_scope")

    try:
        check_scope_policy_stage(
            role,
            action_type,
            policy,
            approved_scope=approved_scope,
            required_roles=required_roles,
            domain_overlay=domain_overlay,
            session_mode=session_mode,
        )
    except ScopeValidationError as exc:
        if (
            allowed_veto_roles
            and role in allowed_veto_roles
            and decision_type == "reject"
        ):
            return
        raise exc
