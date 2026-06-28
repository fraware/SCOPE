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
    assert ctx.role_resolution_source == "caller"
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
    assert not ctx.institutional_authority


def test_claim_hash_stable() -> None:
    claims = {"sub": "a", "iss": "https://idp.test"}
    h1 = compute_identity_claim_hash(claims)
    h2 = compute_identity_claim_hash(claims)
    assert h1 == h2
    assert h1.startswith("sha256:")


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
    assert decision["provenance"]["role_resolution_source"] == "caller"

    grant = engine.issue_grant(packet, decision)
    assert grant["provenance"]["identity_assurance_level"] == IAL0
    assert grant["provenance"]["role_resolution_source"] == "caller"
    assert grant["provenance"]["signing_assurance_level"] == "SAL0"


def test_identity_assurance_schema_validates() -> None:
    from scope.schema_util import validate_artifact

    record = {
        "identity_assurance_level": IAL2,
        "role_resolution_source": "oidc_only",
        "identity_provider": "https://idp.test",
        "identity_claim_hash": compute_identity_claim_hash({"sub": "x"}),
    }
    validate_artifact(record, "identity_assurance.schema.json")
