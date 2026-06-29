"""Pluggable identity providers for institutional OIDC and SAML."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, cast

import yaml

from scope.errors import ScopeValidationError
from scope.identity import VerifiedIdentity, map_claims_to_reviewer, verify_jwt_token


class IdentityProvider(ABC):
    """Resolve and verify reviewer identity from institutional IdP."""

    @abstractmethod
    def verify(self, credential: str) -> VerifiedIdentity:
        """Return verified reviewer identity from bearer credential."""


class OidcProvider(IdentityProvider):
    """OIDC/JWT identity provider (RS256 via JWKS or static PEM)."""

    def __init__(
        self,
        *,
        policy_dir: str | Path,
        jwks_url: str | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        public_key_pem: str | Path | None = None,
    ) -> None:
        self.policy_dir = Path(policy_dir)
        self.jwks_url = jwks_url or os.environ.get("SCOPE_OIDC_JWKS_URL")
        self.issuer = issuer or os.environ.get("SCOPE_OIDC_ISSUER")
        self.audience = audience or os.environ.get("SCOPE_OIDC_AUDIENCE")
        self.public_key_pem = public_key_pem or os.environ.get("SCOPE_OIDC_PUBLIC_KEY_PEM")

    def verify(self, credential: str) -> VerifiedIdentity:
        claims = verify_jwt_token(
            credential,
            jwks_url=self.jwks_url,
            issuer=self.issuer,
            audience=self.audience,
            public_key_pem=self.public_key_pem,
        )
        return map_claims_to_reviewer(claims, policy_dir=self.policy_dir)


class SamlProvider(IdentityProvider):
    """
    Minimal SAML assertion provider.

    Production deployments verify SAML XML via python3-saml or an external sidecar.
    This reference adapter accepts pre-verified assertion JSON from
    ``SCOPE_SAML_ASSERTION_JSON`` or ``--assertion-file``.
    """

    def __init__(
        self,
        *,
        policy_dir: str | Path,
        assertion_path: str | Path | None = None,
    ) -> None:
        self.policy_dir = Path(policy_dir)
        self.assertion_path = assertion_path

    def _load_assertion(self, credential: str) -> dict[str, Any]:
        if credential.strip().startswith("{"):
            loaded = json.loads(credential)
            if loaded:
                return cast(dict[str, Any], loaded)
        path = self.assertion_path or os.environ.get("SCOPE_SAML_ASSERTION_JSON")
        if not path:
            raise ScopeValidationError(
                "SAML provider requires pre-verified assertion JSON via credential, "
                "SCOPE_SAML_ASSERTION_JSON, or assertion_path"
            )
        target = Path(path)
        if not target.is_file():
            raise ScopeValidationError(f"SAML assertion file not found: {target}")
        with target.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) if target.suffix in (".yaml", ".yml") else json.load(fh)
        return cast(dict[str, Any], data if isinstance(data, dict) else {})

    def verify(self, credential: str) -> VerifiedIdentity:
        assertion = self._load_assertion(credential)
        attrs = assertion.get("attributes") or assertion
        reviewer_id = attrs.get("reviewer_id") or attrs.get("name_id") or attrs.get("sub")
        role = attrs.get("role") or attrs.get("scope_role")
        groups = attrs.get("groups") or []
        if not reviewer_id:
            raise ScopeValidationError("SAML assertion missing reviewer_id/name_id")
        claims: dict[str, Any] = {
            "sub": str(reviewer_id),
            "scope_role": role,
            "groups": groups,
        }
        if role:
            claims["scope_role"] = role
        return map_claims_to_reviewer(claims, policy_dir=self.policy_dir)


def resolve_identity_provider(
    provider_name: str,
    *,
    policy_dir: str | Path,
) -> IdentityProvider:
    normalized = provider_name.lower().replace("-", "_")
    if normalized in ("oidc", "jwt", "oidc_jwt"):
        return OidcProvider(policy_dir=policy_dir)
    if normalized in ("saml", "saml2"):
        return SamlProvider(policy_dir=policy_dir)
    raise ScopeValidationError(f"Unknown identity provider: {provider_name}")
