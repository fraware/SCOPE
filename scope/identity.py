"""OIDC/JWT identity verification and claim mapping for institutional trust."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from scope.errors import ScopeValidationError


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _parse_jwt_unverified(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ScopeValidationError("JWT must have header.payload.signature")
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = _b64url_decode(parts[2])
    return header, payload, signing_input, signature


def _load_identity_mapping(policy_dir: str | Path) -> dict[str, Any]:
    path = Path(policy_dir) / "identity_mapping.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _fetch_jwks(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))
    except urllib.error.URLError as exc:
        raise ScopeValidationError(f"Failed to fetch JWKS from {url}: {exc}") from exc


def _jwk_to_public_key(jwk: dict[str, Any]) -> Any:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    if jwk.get("kty") != "RSA":
        raise ScopeValidationError(f"Unsupported JWK kty: {jwk.get('kty')}")
    n = int.from_bytes(_b64url_decode(str(jwk["n"])), "big")
    e = int.from_bytes(_b64url_decode(str(jwk["e"])), "big")
    return RSAPublicNumbers(e, n).public_key()


def _verify_rs256(public_key: Any, signing_input: bytes, signature: bytes) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        public_key.verify(
            signature,
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise ScopeValidationError("JWT signature verification failed") from exc


def _load_static_public_key(path: str | Path) -> Any:
    from cryptography.hazmat.primitives import serialization

    pem = Path(path).read_bytes()
    return serialization.load_pem_public_key(pem)


@dataclass
class VerifiedIdentity:
    reviewer_id: str
    role: str
    claims: dict[str, Any]


def verify_jwt_token(
    token: str,
    *,
    jwks_url: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    public_key_pem: str | Path | None = None,
) -> dict[str, Any]:
    """Verify JWT bearer token and return validated claims."""
    header, payload, signing_input, signature = _parse_jwt_unverified(token)
    alg = header.get("alg")
    if alg != "RS256":
        raise ScopeValidationError(f"Unsupported JWT algorithm: {alg}")

    public_key = None
    if public_key_pem:
        public_key = _load_static_public_key(public_key_pem)
    elif jwks_url:
        jwks = _fetch_jwks(jwks_url)
        keys = jwks.get("keys") or []
        kid = header.get("kid")
        selected = None
        for key in keys:
            if kid and key.get("kid") == kid:
                selected = key
                break
        if selected is None and keys:
            selected = keys[0]
        if selected is None:
            raise ScopeValidationError("No matching JWK found for token")
        public_key = _jwk_to_public_key(selected)
    else:
        raise ScopeValidationError("JWKS URL or static public key PEM required for verification")

    _verify_rs256(public_key, signing_input, signature)

    if issuer and payload.get("iss") != issuer:
        raise ScopeValidationError(f"JWT issuer mismatch: expected {issuer}")
    if audience:
        aud = payload.get("aud")
        if isinstance(aud, list):
            if audience not in aud:
                raise ScopeValidationError(f"JWT audience mismatch: {aud}")
        elif aud != audience:
            raise ScopeValidationError(f"JWT audience mismatch: {aud}")

    exp = payload.get("exp")
    if exp is not None:
        import time

        if time.time() > float(exp):
            raise ScopeValidationError("JWT token expired")

    return payload


def map_claims_to_reviewer(
    claims: dict[str, Any],
    mapping: dict[str, Any] | None = None,
    *,
    policy_dir: str | Path | None = None,
) -> VerifiedIdentity:
    """Map JWT claims to SCOPE reviewer_id and role."""
    cfg = mapping or (_load_identity_mapping(policy_dir) if policy_dir else {})
    mappings = cfg.get("claim_mappings") or {}
    reviewer_claim = mappings.get("reviewer_id", "sub")
    role_claim = mappings.get("role_claim", "scope_role")
    groups_claim = mappings.get("groups_claim", "groups")

    reviewer_id = claims.get(reviewer_claim)
    if not reviewer_id:
        raise ScopeValidationError(f"JWT missing reviewer claim: {reviewer_claim}")

    role = claims.get(role_claim)
    if not role:
        groups = claims.get(groups_claim) or []
        group_map = cfg.get("group_to_role") or {}
        for group in groups:
            mapped = group_map.get(str(group))
            if mapped:
                role = mapped
                break
    if not role:
        role = cfg.get("default_role", "domain_scientist")

    return VerifiedIdentity(
        reviewer_id=str(reviewer_id),
        role=str(role),
        claims=claims,
    )


def verify_token_from_env(token: str, *, policy_dir: str | Path | None = None) -> VerifiedIdentity:
    """Verify token using SCOPE_OIDC_* environment configuration."""
    jwks_url = os.environ.get("SCOPE_OIDC_JWKS_URL")
    issuer = os.environ.get("SCOPE_OIDC_ISSUER")
    audience = os.environ.get("SCOPE_OIDC_AUDIENCE")
    static_pem = os.environ.get("SCOPE_OIDC_PUBLIC_KEY_PEM")
    claims = verify_jwt_token(
        token,
        jwks_url=jwks_url,
        issuer=issuer,
        audience=audience,
        public_key_pem=static_pem,
    )
    return map_claims_to_reviewer(claims, policy_dir=policy_dir)


def apply_identity_to_reviewer(
    reviewer: dict[str, Any],
    identity: VerifiedIdentity,
) -> dict[str, Any]:
    """Override caller-supplied reviewer fields with verified identity."""
    merged = dict(reviewer)
    merged["reviewer_id"] = identity.reviewer_id
    merged["role"] = identity.role
    merged["identity_source"] = "oidc_jwt"
    merged["identity_claims"] = {
        "sub": identity.claims.get("sub"),
        "iss": identity.claims.get("iss"),
    }
    return merged


def oidc_enabled() -> bool:
    value = os.environ.get("SCOPE_OIDC_ENABLED", "").lower()
    return value in ("1", "true", "yes")
