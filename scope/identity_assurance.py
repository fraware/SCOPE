"""Identity assurance levels (IAL) for institutional reviewer provenance."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scope.errors import ScopeValidationError
from scope.hash import compute_hash
from scope.identity import VerifiedIdentity, oidc_enabled
from scope.rbac import resolve_effective_roles_with_provenance
from scope.signing import verify_artifact_signature

IAL0 = "IAL0"
IAL1 = "IAL1"
IAL2 = "IAL2"
IAL3 = "IAL3"
IAL4 = "IAL4"

INSTITUTIONAL_IAL_MIN = IAL3


@dataclass
class IdentityAssuranceContext:
    identity_assurance_level: str
    role_resolution_source: str
    delegation_id: str | None = None
    identity_provider: str | None = None
    identity_claim_hash: str | None = None
    institutional_authority: bool = False

    def to_provenance(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "identity_assurance_level": self.identity_assurance_level,
            "role_resolution_source": self.role_resolution_source,
        }
        if self.delegation_id:
            record["delegation_id"] = self.delegation_id
        if self.identity_provider:
            record["identity_provider"] = self.identity_provider
        if self.identity_claim_hash:
            record["identity_claim_hash"] = self.identity_claim_hash
        return record


def compute_identity_claim_hash(claims: dict[str, Any]) -> str:
    """Canonical SHA-256 hash of identity claims for audit linkage."""
    payload = {k: claims[k] for k in sorted(claims.keys())}
    return compute_hash({"claims": payload})


def _has_valid_decision_signature(decision: dict[str, Any] | None) -> bool:
    if not decision or not decision.get("decision_signature"):
        return False
    from scope.signing import Ed25519PublicVerifier

    ref = decision.get("reviewer_public_key_ref")
    if not ref:
        return False
    try:
        verifier = Ed25519PublicVerifier(ref)
        return verify_artifact_signature(
            decision,
            verifier,
            hash_field="decision_hash",
            signature_field="decision_signature",
        )
    except Exception:
        return False


def resolve_identity_assurance(
    reviewer: dict[str, Any],
    *,
    policy_dir: str | Path,
    identity: VerifiedIdentity | None = None,
    decision: dict[str, Any] | None = None,
    enforce_institutional: bool = False,
) -> IdentityAssuranceContext:
    """
    Determine identity assurance level from reviewer input, OIDC, RBAC, and signatures.

    Caller-supplied JSON alone is IAL0 and is not institutional authority.
  """
    role = str(reviewer.get("role", ""))
    reviewer_id = str(reviewer.get("reviewer_id", ""))
    signed = _has_valid_decision_signature(decision)

    if identity is None and not signed:
        return IdentityAssuranceContext(
            identity_assurance_level=IAL0,
            role_resolution_source="caller",
            institutional_authority=False,
        )

    if identity is None and signed:
        return IdentityAssuranceContext(
            identity_assurance_level=IAL1,
            role_resolution_source="local_signature",
            institutional_authority=False,
        )

    if identity is None:
        raise ScopeValidationError("Internal error: identity required for OIDC assurance path")

    claims = identity.claims
    claim_hash = compute_identity_claim_hash(claims)
    provider = str(claims.get("iss") or reviewer.get("identity_source") or "oidc")

    role_info = resolve_effective_roles_with_provenance(
        reviewer_id,
        role,
        policy_dir,
    )
    effective_roles = role_info["effective_roles"]
    source = role_info["role_resolution_source"]
    delegation_id = role_info.get("delegation_id")

    if role not in effective_roles:
        if enforce_institutional:
            raise ScopeValidationError(
                f"OIDC identity verified but reviewer {reviewer_id} lacks institutional "
                f"role {role} (effective: {sorted(effective_roles)})"
            )
        return IdentityAssuranceContext(
            identity_assurance_level=IAL2,
            role_resolution_source="oidc_only",
            identity_provider=provider,
            identity_claim_hash=claim_hash,
            institutional_authority=False,
        )

    if source == "delegation" and delegation_id:
        return IdentityAssuranceContext(
            identity_assurance_level=IAL4,
            role_resolution_source="org_rbac",
            delegation_id=delegation_id,
            identity_provider=provider,
            identity_claim_hash=claim_hash,
            institutional_authority=True,
        )

    return IdentityAssuranceContext(
        identity_assurance_level=IAL3,
        role_resolution_source="org_rbac",
        identity_provider=provider,
        identity_claim_hash=claim_hash,
        institutional_authority=True,
    )


def merge_identity_provenance(
    artifact: dict[str, Any],
    context: IdentityAssuranceContext,
) -> dict[str, Any]:
    """Attach identity assurance fields to decision or grant provenance."""
    provenance = dict(artifact.get("provenance") or {})
    provenance.update(context.to_provenance())
    artifact = dict(artifact)
    artifact["provenance"] = provenance
    return artifact


def is_institutional_assurance(level: str) -> bool:
    return level in (IAL3, IAL4)


def identity_assurance_from_env_enabled() -> bool:
    return oidc_enabled()
