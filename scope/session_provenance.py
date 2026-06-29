"""Aggregate provenance from multi-reviewer session grants."""

from __future__ import annotations

from typing import Any

from scope.errors import GrantValidationError
from scope.hash import compute_hash
from scope.identity_assurance import IAL0, IAL1, IAL2, IAL3, IAL4
from scope.review_session import ReviewSession
from scope.signing_assurance import SAL0, SAL1, SAL2, SAL3, SAL4, resolve_signing_assurance_level

IAL_RANK = {IAL0: 0, IAL1: 1, IAL2: 2, IAL3: 3, IAL4: 4}
SAL_RANK = {SAL0: 0, SAL1: 1, SAL2: 2, SAL3: 3, SAL4: 4}

SESSION_PROVENANCE_FIELDS = (
    "contributing_identity_assurance_levels",
    "contributing_authority_checks",
    "minimum_identity_assurance_level",
    "minimum_signing_assurance_level",
    "veto_roles_applied",
    "quorum_policy_hash",
)


def is_session_grant_provenance(provenance: dict[str, Any]) -> bool:
    """True when provenance carries session aggregation markers."""
    levels = provenance.get("contributing_identity_assurance_levels")
    return isinstance(levels, list) and len(levels) > 0


def validate_session_grant_provenance(provenance: dict[str, Any]) -> None:
    """Runtime check: session grants must include full provenance block."""
    if not is_session_grant_provenance(provenance):
        return
    missing = [field for field in SESSION_PROVENANCE_FIELDS if field not in provenance]
    if missing:
        raise GrantValidationError(
            "Session grant provenance missing required fields: "
            + ", ".join(sorted(missing))
        )
    if not provenance["contributing_identity_assurance_levels"]:
        raise GrantValidationError(
            "Session grant provenance requires non-empty "
            "contributing_identity_assurance_levels"
        )
    if not provenance["contributing_authority_checks"]:
        raise GrantValidationError(
            "Session grant provenance requires non-empty contributing_authority_checks"
        )
    if not str(provenance["quorum_policy_hash"]).startswith("sha256:"):
        raise GrantValidationError("Session grant provenance quorum_policy_hash invalid")


def _minimum_level(levels: list[str], rank: dict[str, int], default: str) -> str:
    if not levels:
        return default
    return min(levels, key=lambda level: rank.get(level, -1))


def aggregate_session_grant_provenance(
    session: ReviewSession,
    contributing_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build session-specific provenance fields for a multi-reviewer grant."""
    contributing_identity_assurance_levels: list[dict[str, Any]] = []
    contributing_authority_checks: list[dict[str, Any]] = []
    identity_levels: list[str] = []
    signing_levels: list[str] = []

    for decision in contributing_decisions:
        reviewer = decision.get("reviewer") or {}
        reviewer_id = reviewer.get("reviewer_id", "")
        decision_id = decision.get("decision_id", "")
        dec_prov = decision.get("provenance") or {}
        ial = str(dec_prov.get("identity_assurance_level", IAL0))
        identity_levels.append(ial)
        contributing_identity_assurance_levels.append(
            {
                "decision_id": decision_id,
                "reviewer_id": reviewer_id,
                "reviewer_role": reviewer.get("role"),
                "identity_assurance_level": ial,
                "role_resolution_source": dec_prov.get("role_resolution_source"),
                "identity_source": dec_prov.get("identity_source"),
            }
        )
        authority_checks = dec_prov.get("authority_checks")
        if authority_checks is not None:
            contributing_authority_checks.append(
                {
                    "decision_id": decision_id,
                    "reviewer_id": reviewer_id,
                    "authority_checks": authority_checks,
                }
            )
        signing_levels.append(
            resolve_signing_assurance_level(
                decision,
                reviewer_id=reviewer_id or None,
            )
        )

    veto_roles = session.quorum_policy.get("safety_veto_roles") or []

    return {
        "contributing_identity_assurance_levels": contributing_identity_assurance_levels,
        "contributing_authority_checks": contributing_authority_checks,
        "minimum_identity_assurance_level": _minimum_level(identity_levels, IAL_RANK, IAL0),
        "minimum_signing_assurance_level": _minimum_level(signing_levels, SAL_RANK, SAL0),
        "veto_roles_applied": list(veto_roles),
        "quorum_policy_hash": compute_hash(session.quorum_policy),
    }
