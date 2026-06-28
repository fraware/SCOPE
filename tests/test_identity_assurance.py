"""Tests for identity assurance levels."""

from __future__ import annotations

from pathlib import Path

from scope.identity import VerifiedIdentity
from scope.identity_assurance import (
    IAL0,
    IAL2,
    IAL3,
    IAL4,
    compute_identity_claim_hash,
    resolve_identity_assurance,
)

ROOT = Path(__file__).resolve().parent.parent


def test_ial0_caller_supplied_only() -> None:
    ctx = resolve_identity_assurance(
        {"reviewer_id": "caller1", "role": "domain_scientist"},
        policy_dir=ROOT / "policy",
    )
    assert ctx.identity_assurance_level == IAL0
    assert ctx.role_resolution_source == "caller_supplied"
    assert ctx.identity_source == "caller_json"
    assert not ctx.institutional_authority


def test_ial3_oidc_with_directory_role() -> None:
    claims = {"sub": "ds1", "iss": "https://idp.test", "scope_role": "domain_scientist"}
    identity = VerifiedIdentity(
        reviewer_id="ds1",
        role="domain_scientist",
        claims=claims,
    )
    ctx = resolve_identity_assurance(
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        policy_dir=ROOT / "policy",
        identity=identity,
    )
    assert ctx.identity_assurance_level == IAL3
    assert ctx.institutional_authority
    assert ctx.identity_source == "oidc_jwt"
    assert ctx.role_resolution_source == "org_rbac"
    assert ctx.identity_claim_hash.startswith("sha256:")


def test_ial4_delegated_role() -> None:
    claims = {"sub": "ds2", "iss": "https://idp.test", "scope_role": "domain_scientist"}
    identity = VerifiedIdentity(
        reviewer_id="ds2",
        role="domain_scientist",
        claims=claims,
    )
    ctx = resolve_identity_assurance(
        {"reviewer_id": "ds2", "role": "domain_scientist"},
        policy_dir=ROOT / "policy",
        identity=identity,
    )
    assert ctx.identity_assurance_level == IAL4
    assert ctx.delegation_id is not None
    assert ctx.institutional_authority
    assert ctx.identity_source == "oidc_jwt"


def test_ial2_oidc_without_directory_role() -> None:
    claims = {"sub": "unknown", "iss": "https://idp.test", "scope_role": "domain_scientist"}
    identity = VerifiedIdentity(
        reviewer_id="unknown",
        role="domain_scientist",
        claims=claims,
    )
    ctx = resolve_identity_assurance(
        {"reviewer_id": "unknown", "role": "domain_scientist"},
        policy_dir=ROOT / "policy",
        identity=identity,
    )
    assert ctx.identity_assurance_level == IAL2
    assert ctx.role_resolution_source == "oidc_verified"
    assert ctx.identity_source == "oidc_jwt"
    assert not ctx.institutional_authority


def test_claim_hash_stable() -> None:
    claims = {"sub": "a", "iss": "https://idp.test"}
    h1 = compute_identity_claim_hash(claims)
    h2 = compute_identity_claim_hash(claims)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_ial1_local_signed_key_upgrades_after_sign(tmp_path: Path) -> None:
    from scope import ScopeEngine
    from scope.identity_assurance import IAL1
    from scope.signing import Ed25519Signer

    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    packet = engine.create_packet(
        {"record_id": "IAL1-SIGN", "scientific_action_type": "A5_protocol_modification"},
        trigger,
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "unsigned submit stays IAL0",
        },
    )
    assert decision["provenance"]["identity_assurance_level"] == IAL0

    signed = engine.sign_decision(decision, Ed25519Signer(key))
    assert signed["provenance"]["identity_assurance_level"] == IAL1
    assert signed["provenance"]["role_resolution_source"] == "local_signed_key"
    assert signed["provenance"]["identity_source"] == "local_signed_key"

    grant = engine.issue_grant(packet, signed)
    assert grant["provenance"]["identity_assurance_level"] == IAL1
    assert grant["provenance"]["identity_source"] == "local_signed_key"
    assert grant["provenance"]["authority_checks"] == signed["provenance"]["authority_checks"]


def test_decision_and_grant_record_identity_provenance(tmp_path) -> None:
    from scope import ScopeEngine

    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    packet = engine.create_packet(
        {"record_id": "IAL-GRANT", "scientific_action_type": "A5_protocol_modification"},
        trigger,
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "caller1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "caller-supplied reviewer",
        },
    )
    assert decision["provenance"]["identity_assurance_level"] == IAL0
    assert decision["provenance"]["role_resolution_source"] == "caller_supplied"
    assert decision["provenance"]["identity_source"] == "caller_json"
    assert "authority_checks" in decision["provenance"]

    grant = engine.issue_grant(packet, decision)
    assert grant["provenance"]["identity_assurance_level"] == IAL0
    assert grant["provenance"]["role_resolution_source"] == "caller_supplied"
    assert grant["provenance"]["identity_source"] == "caller_json"
    assert grant["provenance"]["signing_assurance_level"] == "SAL0"
    assert grant["provenance"]["authority_checks"]["scope_role_valid"] is True


def test_identity_assurance_schema_validates() -> None:
    from scope.schema_util import validate_artifact

    record = {
        "identity_assurance_level": IAL2,
        "role_resolution_source": "oidc_verified",
        "identity_source": "oidc_jwt",
        "identity_claim_hash": compute_identity_claim_hash({"sub": "x"}),
    }
    validate_artifact(record, "identity_assurance.schema.json")


def test_oidc_grant_inherits_identity_claim_hash_and_authority_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import time

    from tests.jwt_helpers import build_rs256_jwt, generate_rsa_keypair

    private_key, public_pem = generate_rsa_keypair()
    pem_path = tmp_path / "oidc.pub"
    pem_path.write_bytes(public_pem)
    monkeypatch.setenv("SCOPE_OIDC_PUBLIC_KEY_PEM", str(pem_path))
    monkeypatch.setenv("SCOPE_OIDC_ISSUER", "https://idp.test")
    monkeypatch.setenv("SCOPE_OIDC_AUDIENCE", "scope")

    from scope import ScopeEngine

    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A4_recommendation",
        "requested_action": "draft_recommendation",
        "requested_tool": "recommendation.draft",
        "requested_scope": "draft_recommendation",
    }
    packet = engine.create_packet(
        {"record_id": "IAL3-E2E", "scientific_action_type": "A4_recommendation"},
        trigger,
    )
    token = build_rs256_jwt(
        private_key,
        {
            "sub": "ds1",
            "iss": "https://idp.test",
            "aud": "scope",
            "scope_role": "domain_scientist",
            "exp": int(time.time()) + 3600,
        },
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve",
            "approved_scope": "draft_recommendation",
            "rationale": "OIDC plus org RBAC",
        },
        identity_token=token,
        enforce_rbac=True,
    )
    grant = engine.issue_grant(packet, decision)

    claim_hash = decision["provenance"]["identity_claim_hash"]
    assert claim_hash.startswith("sha256:")
    assert grant["provenance"]["identity_claim_hash"] == claim_hash
    assert grant["provenance"]["identity_assurance_level"] == IAL3
    assert grant["provenance"]["identity_source"] == "oidc_jwt"
    assert grant["provenance"]["authority_checks"] == decision["provenance"]["authority_checks"]
    assert grant["provenance"]["authority_checks"]["rbac_enforced"] is True


def test_ial4_grant_inherits_delegation_provenance(tmp_path: Path, monkeypatch) -> None:
    import time

    from tests.jwt_helpers import build_rs256_jwt, generate_rsa_keypair

    private_key, public_pem = generate_rsa_keypair()
    pem_path = tmp_path / "oidc.pub"
    pem_path.write_bytes(public_pem)
    monkeypatch.setenv("SCOPE_OIDC_PUBLIC_KEY_PEM", str(pem_path))
    monkeypatch.setenv("SCOPE_OIDC_ISSUER", "https://idp.test")
    monkeypatch.setenv("SCOPE_OIDC_AUDIENCE", "scope")

    from scope import ScopeEngine

    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A4_recommendation",
        "requested_action": "draft_recommendation",
        "requested_tool": "recommendation.draft",
        "requested_scope": "draft_recommendation",
    }
    packet = engine.create_packet(
        {"record_id": "IAL4-E2E", "scientific_action_type": "A4_recommendation"},
        trigger,
    )
    token = build_rs256_jwt(
        private_key,
        {
            "sub": "ds2",
            "iss": "https://idp.test",
            "aud": "scope",
            "scope_role": "domain_scientist",
            "exp": int(time.time()) + 3600,
        },
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "ds2", "role": "domain_scientist"},
        {
            "type": "approve",
            "approved_scope": "draft_recommendation",
            "rationale": "Delegated org RBAC role",
        },
        identity_token=token,
        enforce_rbac=True,
    )
    grant = engine.issue_grant(packet, decision)

    assert decision["provenance"]["identity_assurance_level"] == IAL4
    assert decision["provenance"]["delegation_id"] == "ds1"
    assert grant["provenance"]["delegation_id"] == "ds1"
    assert grant["provenance"]["authority_checks"]["delegation_id"] == "ds1"
