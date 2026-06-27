"""Tests for signed decisions and grants (Priority 4)."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import ScopeValidationError
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_sign_and_verify_decision(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    signer = Ed25519Signer(key)
    signed = engine.sign_decision(decision, signer)
    assert signed["decision_signature"]
    assert signed["signature_algorithm"] == "ed25519"
    assert engine.verify_decision(signed, signer)


def test_sign_and_verify_grant(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    signer = Ed25519Signer(key)
    signed = engine.sign_grant(grant, signer)
    assert signed["grant_signature"]
    assert engine.verify_grant(signed, signer)


def test_tamper_detection(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    signer = Ed25519Signer(key)
    signed = engine.sign_decision(decision, signer)
    signed["decision_hash"] = "sha256:" + "0" * 64
    assert not engine.verify_decision(signed, signer)


def test_production_mode_rejects_unsigned(monkeypatch):
    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    with pytest.raises(ScopeValidationError, match="decision_signature"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "r1", "role": "protocol_owner"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "protocol_draft",
                "rationale": "ok",
            },
        )


def test_pcs_export_includes_signatures(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    from adapters.pcs.export_artifact import export_pcs_artifact

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    signer = Ed25519Signer(key)
    signed_dec = engine.sign_decision(decision, signer)
    grant = engine.issue_grant(packet, signed_dec)
    signed_grant = engine.sign_grant(grant, signer)
    out = export_pcs_artifact(packet, signed_dec, signed_grant, tmp_path / "pcs")
    import json

    manifest = json.loads((out / "release_manifest.json").read_text())
    assert manifest.get("decision_signature")
    assert manifest.get("grant_signature")
