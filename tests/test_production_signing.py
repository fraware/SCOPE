"""Tests for production signing semantics (SCOPE-1)."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import GrantValidationError, ScopeValidationError

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_unsigned_decision_ok_in_production_mode(monkeypatch):
    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    assert decision.get("signature_required") is True
    assert "decision_signature" not in decision


def test_unsigned_decision_cannot_issue_grant_in_production(monkeypatch):
    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    with pytest.raises(GrantValidationError, match="signed decision"):
        engine.issue_grant(packet, decision)


def test_signed_decision_can_issue_grant_in_production(tmp_path, monkeypatch):
    from scope.signing import Ed25519Signer

    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    grant = engine.issue_grant(packet, signed)
    assert grant["grant_id"].startswith("SCOPE-GRANT-")


def test_decision_validate_require_signature(monkeypatch):
    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    engine.validate_decision(decision)
    with pytest.raises(ScopeValidationError, match="decision_signature"):
        engine.validate_decision(decision, require_signature=True)


def test_readme_signing_sequence(tmp_path, monkeypatch):
    """submit unsigned -> sign -> grant issue works in production mode."""
    from scope.signing import Ed25519Signer

    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    grant = engine.issue_grant(packet, signed)
    assert grant["authorization"]["approved_scope"] == "protocol_draft"


def test_session_grant_includes_contributing_signatures_in_production(tmp_path, monkeypatch):
    from scope.signing import Ed25519Signer

    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    key_ds = tmp_path / "ds.pem"
    pub_ds = tmp_path / "ds.pub"
    key_po = tmp_path / "po.pem"
    pub_po = tmp_path / "po.pub"
    Ed25519Signer.generate_keypair(key_ds, pub_ds)
    Ed25519Signer.generate_keypair(key_po, pub_po)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
    }
    record = {"record_id": "AKTA-PROD-SESS", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    session = engine.create_review_session(packet)

    d1 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    d2 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    signed = [
        engine.sign_decision(d1, Ed25519Signer(key_ds)),
        engine.sign_decision(d2, Ed25519Signer(key_po)),
    ]
    grant = engine.issue_grant_from_session(session, packet, signed)
    assert "contributing_signatures" in grant
    assert len(grant["contributing_signatures"]) == 2
    for entry in grant["contributing_signatures"]:
        assert entry.get("decision_signature")
        assert entry.get("reviewer_public_key_ref")
