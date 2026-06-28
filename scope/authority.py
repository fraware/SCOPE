"""Two-stage institutional authority: org RBAC then SCOPE scope policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scope.errors import RoleValidationError, ScopeValidationError
from scope.identity_assurance import IdentityAssuranceContext, is_institutional_assurance
from scope.policy import PolicyStore
from scope.rbac import check_rbac_permission, resolve_effective_roles_with_provenance
from scope.roles import validate_reviewer_for_action, validate_reviewer_for_scope


@dataclass
class AuthorityCheckResult:
    """Explicit two-stage authority check outcomes for decision/grant provenance."""

    rbac_enforced: bool
    rbac_role_valid: bool
    scope_role_valid: bool
    scope_approval_valid: bool
    delegation_id: str | None = None

    def to_provenance_block(self) -> dict[str, Any]:
        return {
            "authority_checks": {
                "rbac_enforced": self.rbac_enforced,
                "rbac_role_valid": self.rbac_role_valid,
                "scope_role_valid": self.scope_role_valid,
                "scope_approval_valid": self.scope_approval_valid,
                "delegation_id": self.delegation_id,
            }
        }


def merge_authority_provenance(
    artifact: dict[str, Any],
    result: AuthorityCheckResult,
) -> dict[str, Any]:
    """Attach authority_checks to decision or grant provenance."""
    provenance = dict(artifact.get("provenance") or {})
    provenance.update(result.to_provenance_block())
    updated = dict(artifact)
    updated["provenance"] = provenance
    return updated


def _check_rbac_stage(
    reviewer_id: str,
    role: str,
    action: str,
    policy_dir: str | Path,
    *,
    at: datetime | None = None,
) -> tuple[bool, str | None]:
    """Return (rbac_role_valid, delegation_id) or raise ScopeValidationError."""
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
    delegation_id = role_info.get("delegation_id")
    if role_info.get("role_resolution_source") == "delegation" and delegation_id:
        return True, str(delegation_id)
    return True, None


def _check_scope_role_stage(
    role: str,
    action_type: str,
    policy: PolicyStore,
    *,
    required_roles: list[str] | None = None,
    domain_overlay: str | None = None,
) -> bool:
    try:
        validate_reviewer_for_action(
            role,
            action_type,
            policy,
            required_roles=required_roles,
            domain_overlay=domain_overlay,
        )
        return True
    except RoleValidationError as exc:
        raise ScopeValidationError(f"SCOPE policy authority: {exc}") from exc


def _check_scope_approval_stage(
    role: str,
    approved_scope: str | None,
    policy: PolicyStore,
    *,
    session_mode: bool = False,
) -> bool:
    if not approved_scope:
        return True
    try:
        validate_reviewer_for_scope(
            role,
            approved_scope,
            policy,
            session_mode=session_mode,
        )
        return True
    except (RoleValidationError, ScopeValidationError) as exc:
        raise ScopeValidationError(f"SCOPE scope authority: {exc}") from exc


def run_authority_checks(
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
) -> AuthorityCheckResult:
    """
    Run two-stage authority checks and return explicit outcomes for provenance.

    Raises ScopeValidationError when a required check fails.
    """
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

    rbac_role_valid = False
    delegation_id: str | None = None
    if should_enforce_rbac:
        if identity_context and not identity_context.institutional_authority:
            if not is_institutional_assurance(identity_context.identity_assurance_level):
                should_enforce_rbac = False
        if should_enforce_rbac:
            rbac_role_valid, delegation_id = _check_rbac_stage(
                reviewer_id,
                role,
                rbac_action,
                policy.policy_dir,
                at=at,
            )
            if delegation_id is None and identity_context and identity_context.delegation_id:
                delegation_id = identity_context.delegation_id

    approved_scope = None
    if policy.is_approval_decision(decision_type):
        approved_scope = decision_input.get("approved_scope")

    scope_role_valid = False
    scope_approval_valid = False
    try:
        scope_role_valid = _check_scope_role_stage(
            role,
            action_type,
            policy,
            required_roles=required_roles,
            domain_overlay=domain_overlay,
        )
        scope_approval_valid = _check_scope_approval_stage(
            role,
            approved_scope,
            policy,
            session_mode=session_mode,
        )
    except ScopeValidationError as exc:
        if (
            allowed_veto_roles
            and role in allowed_veto_roles
            and decision_type == "reject"
        ):
            return AuthorityCheckResult(
                rbac_enforced=should_enforce_rbac,
                rbac_role_valid=rbac_role_valid,
                scope_role_valid=True,
                scope_approval_valid=True,
                delegation_id=delegation_id,
            )
        raise exc

    return AuthorityCheckResult(
        rbac_enforced=should_enforce_rbac,
        rbac_role_valid=rbac_role_valid,
        scope_role_valid=scope_role_valid,
        scope_approval_valid=scope_approval_valid,
        delegation_id=delegation_id,
    )


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
) -> AuthorityCheckResult:
    """Run two-stage authority checks before accepting a decision."""
    return run_authority_checks(
        reviewer,
        packet,
        decision_input,
        policy,
        identity_context=identity_context,
        enforce_rbac=enforce_rbac,
        session_mode=session_mode,
        allowed_veto_roles=allowed_veto_roles,
        at=at,
    )
