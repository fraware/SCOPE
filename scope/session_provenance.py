"""Aggregate provenance from multi-reviewer session grants."""

from __future__ import annotations

from typing import Any

from scope.hash import compute_hash
from scope.identity_assurance import IAL0, IAL1, IAL2, IAL3, IAL4
from scope.review_session import ReviewSession
from scope.signing_assurance import SAL0, SAL1, SAL2, SAL3, SAL4, resolve_signing_assurance_level

IAL_RANK = {IAL0: 0, IAL1: 1, IAL2: 2, IAL3: 3, IAL4: 4}
SAL_RANK = {SAL0: 0, SAL1: 1, SAL2: 2, SAL3: 3, SAL4: 4}


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
