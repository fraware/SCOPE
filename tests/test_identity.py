"""Tests for OIDC/JWT identity verification."""

from __future__ import annotations

import tempfile
from pathlib import Path

from scope.identity import map_claims_to_reviewer, verify_jwt_token
from tests.jwt_helpers import build_rs256_jwt, generate_rsa_keypair


def test_verify_jwt_with_static_pem() -> None:
    private_key, public_pem = generate_rsa_keypair()
    claims = {
        "sub": "reviewer-42",
        "scope_role": "domain_scientist",
        "iss": "https://idp.example.test",
        "aud": "scope-api",
        "exp": int(__import__("time").time()) + 3600,
    }
    token = build_rs256_jwt(private_key, claims)
    with tempfile.TemporaryDirectory() as tmp:
        pem_path = Path(tmp) / "idp.pub"
        pem_path.write_bytes(public_pem)
        verified = verify_jwt_token(
            token,
            issuer="https://idp.example.test",
            audience="scope-api",
            public_key_pem=pem_path,
        )
    identity = map_claims_to_reviewer(verified, policy_dir="policy/")
    assert identity.reviewer_id == "reviewer-42"
    assert identity.role == "domain_scientist"


def test_map_groups_to_role() -> None:
    claims = {"sub": "u1", "groups": ["scope-system-owner"]}
    mapping = {
        "claim_mappings": {"reviewer_id": "sub", "groups_claim": "groups"},
        "group_to_role": {"scope-system-owner": "system_owner"},
    }
    identity = map_claims_to_reviewer(claims, mapping)
    assert identity.role == "system_owner"
