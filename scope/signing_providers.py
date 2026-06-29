"""Pluggable signing key providers for institutional key management."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from scope.errors import ScopeValidationError
from scope.signing import Ed25519Signer, Signer


class SigningProvider(ABC):
    """Resolve Ed25519 signers from configured backends."""

    @abstractmethod
    def get_signer(self, *, reviewer_id: str | None = None) -> Signer:
        """Return a signer for the given reviewer."""


class LocalPemProvider(SigningProvider):
    """Sign with an explicit local PEM private key path."""

    def __init__(self, private_key_path: str | Path) -> None:
        self.private_key_path = Path(private_key_path)

    def get_signer(self, *, reviewer_id: str | None = None) -> Signer:
        if not self.private_key_path.is_file():
            raise ScopeValidationError(f"Signing key not found: {self.private_key_path}")
        return Ed25519Signer(self.private_key_path)


class EnvKeyProvider(SigningProvider):
    """Sign using SCOPE_SIGNING_KEY environment variable."""

    def __init__(self, env_var: str = "SCOPE_SIGNING_KEY") -> None:
        self.env_var = env_var

    def get_signer(self, *, reviewer_id: str | None = None) -> Signer:
        key_path = os.environ.get(self.env_var)
        if not key_path:
            raise ScopeValidationError(f"{self.env_var} not set")
        from scope.signing_assurance import emit_env_key_warning

        emit_env_key_warning()
        return LocalPemProvider(key_path).get_signer(reviewer_id=reviewer_id)


class RegistryKeyProvider(SigningProvider):
    """Resolve private key path from reviewer_key_registry signing_key_path (pilot only)."""

    def __init__(self, policy_dir: str | Path, *, reviewer_id: str) -> None:
        self.policy_dir = Path(policy_dir)
        self.reviewer_id = reviewer_id

    def get_signer(self, *, reviewer_id: str | None = None) -> Signer:
        from scope.policy import PolicyStore

        rid = reviewer_id or self.reviewer_id
        policy = PolicyStore.from_dir(self.policy_dir)
        entry = policy.reviewer_key_registry_entries.get(rid)
        if entry is None:
            raise ScopeValidationError(f"No registry entry for reviewer_id {rid}")
        key_path = entry.get("signing_key_path")
        if not key_path:
            raise ScopeValidationError(
                f"Registry entry for {rid} has no signing_key_path "
                "(institutional pilot only; not for production)"
            )
        resolved = Path(str(key_path))
        if not resolved.is_absolute():
            resolved = self.policy_dir / resolved
        return LocalPemProvider(resolved).get_signer(reviewer_id=rid)


class KmsSigningProvider(SigningProvider):
    """
    Reference KMS signing adapter (SAL4).

    Uses ``SCOPE_KMS_REFERENCE_KEY_PATH`` for local reference signing in dev/test,
    or ``SCOPE_KMS_ENDPOINT`` + ``SCOPE_KMS_KEY_ID`` for institutional KMS HTTP boundary.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        key_id: str | None = None,
        reference_key_path: str | Path | None = None,
    ) -> None:
        self.endpoint = endpoint or os.environ.get("SCOPE_KMS_ENDPOINT")
        self.key_id = key_id or os.environ.get("SCOPE_KMS_KEY_ID")
        ref = reference_key_path or os.environ.get("SCOPE_KMS_REFERENCE_KEY_PATH")
        self.reference_key_path = Path(ref) if ref else None

    def get_signer(self, *, reviewer_id: str | None = None) -> Signer:
        if self.reference_key_path and self.reference_key_path.is_file():
            return Ed25519Signer(self.reference_key_path)
        if self.endpoint and self.key_id:
            from scope.signing_assurance import KmsHttpSigner

            return KmsHttpSigner(endpoint=self.endpoint, key_id=self.key_id)
        raise ScopeValidationError(
            "KMS signing requires SCOPE_KMS_REFERENCE_KEY_PATH (reference) or "
            "SCOPE_KMS_ENDPOINT + SCOPE_KMS_KEY_ID (institutional boundary)"
        )


def resolve_signing_provider(
    provider_name: str,
    *,
    policy_dir: str | Path,
    key_path: str | Path | None = None,
    reviewer_id: str | None = None,
) -> SigningProvider:
    """Factory for signing providers."""
    normalized = provider_name.lower().replace("-", "_")
    if normalized in ("local", "local_pem", "pem"):
        if not key_path:
            raise ScopeValidationError("local signing provider requires --key or --signing-key")
        return LocalPemProvider(key_path)
    if normalized in ("env", "env_key"):
        return EnvKeyProvider()
    if normalized in ("registry", "registry_key"):
        if not reviewer_id:
            raise ScopeValidationError("registry signing provider requires --reviewer-id")
        return RegistryKeyProvider(policy_dir, reviewer_id=reviewer_id)
    if normalized in ("kms", "hsm", "hsm_kms", "kms_sign"):
        return KmsSigningProvider()
    raise ScopeValidationError(f"Unknown signing provider: {provider_name}")
