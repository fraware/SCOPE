"""Signing assurance levels (SAL) for decision and grant provenance."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from scope.errors import GrantValidationError, ScopeValidationError
from scope.signing import verify_artifact_signature

logger = logging.getLogger(__name__)

SAL0 = "SAL0"
SAL1 = "SAL1"
SAL2 = "SAL2"
SAL3 = "SAL3"
SAL4 = "SAL4"

SAL_RANK = {SAL0: 0, SAL1: 1, SAL2: 2, SAL3: 3, SAL4: 4}


def load_minimum_signing_assurance(policy_dir: str | Path) -> dict[str, Any]:
    path = Path(policy_dir) / "minimum_signing_assurance.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_signing_assurance_level(
    artifact: dict[str, Any],
    *,
    provider_name: str | None = None,
    reviewer_id: str | None = None,
) -> str:
    """Infer SAL from artifact signatures and signing provider metadata."""
    signature_field = "decision_signature" if "decision_id" in artifact else "grant_signature"
    hash_field = "decision_hash" if signature_field == "decision_signature" else "grant_hash"

    if not artifact.get(signature_field):
        return SAL0

    normalized_provider = (provider_name or "").lower().replace("-", "_")
    provenance = artifact.get("provenance") or {}
    stored_level = provenance.get("signing_assurance_level")
    if stored_level in SAL_RANK:
        return str(stored_level)

    if normalized_provider in ("hsm", "kms", "hsm_kms"):
        return SAL4

    if normalized_provider in ("registry", "registry_key"):
        rid = reviewer_id or (artifact.get("reviewer") or {}).get("reviewer_id")
        ref = artifact.get("reviewer_public_key_ref")
        if rid and ref:
            return SAL3
        return SAL1

    if normalized_provider in ("env", "env_key"):
        emit_env_key_warning()
        return SAL2

    if normalized_provider in ("local", "local_pem", "pem", ""):
        if artifact.get(signature_field) and artifact.get("reviewer_public_key_ref"):
            from scope.signing import Ed25519PublicVerifier

            try:
                verifier = Ed25519PublicVerifier(str(artifact["reviewer_public_key_ref"]))
                if verify_artifact_signature(
                    artifact,
                    verifier,
                    hash_field=hash_field,
                    signature_field=signature_field,
                ):
                    return SAL1
            except Exception:
                return SAL0
        return SAL1 if artifact.get(signature_field) else SAL0

    return SAL1 if artifact.get(signature_field) else SAL0


def emit_env_key_warning() -> None:
    logger.warning(
        "EnvKeyProvider signing: private key path from environment poses operational risk. "
        "Use HSM/KMS (SAL4) or registry-bound keys (SAL3) for production."
    )


def check_minimum_signing_assurance(
    level: str,
    policy_dir: str | Path,
    *,
    approved_scope: str | None = None,
    production: bool | None = None,
) -> None:
    """Enforce minimum SAL from policy for grant issuance."""
    from scope.config import is_production_mode

    cfg = load_minimum_signing_assurance(policy_dir)
    if production is None:
        production = is_production_mode()
    if not production and not cfg.get("enforce_in_development"):
        return

    minimum = str(cfg.get("minimum_level", SAL1))
    high_risk_scopes = cfg.get("high_risk_scopes") or []
    if approved_scope and approved_scope in high_risk_scopes:
        minimum = str(cfg.get("high_risk_minimum_level", SAL3))

    if SAL_RANK.get(level, 0) < SAL_RANK.get(minimum, 1):
        raise GrantValidationError(
            f"Signing assurance {level} below required minimum {minimum} "
            f"for scope {approved_scope or 'grant'}"
        )


def merge_signing_provenance(
    artifact: dict[str, Any],
    level: str,
) -> dict[str, Any]:
    provenance = dict(artifact.get("provenance") or {})
    provenance["signing_assurance_level"] = level
    result = dict(artifact)
    result["provenance"] = provenance
    return result


class HsmKmsSigningProvider:
    """
    External HSM/KMS signing interface (SAL4).

    Production deployments integrate vendor SDKs behind this boundary.
    SCOPE does not ship a fake HSM implementation.
    """

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.environ.get("SCOPE_HSM_ENDPOINT")

    def get_signer(self, *, reviewer_id: str | None = None) -> Any:
        raise ScopeValidationError(
            "HSM/KMS signing (SAL4) requires external provider integration. "
            "Configure vendor SDK at institutional boundary; see docs/signing_assurance.md."
        )
