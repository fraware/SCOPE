"""Tests for public-key verification (SCOPE-4)."""

from pathlib import Path

from scope import ScopeEngine
from scope.signing import Ed25519PublicVerifier, Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_public_key_verify_decision(tmp_path):
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
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    verifier = Ed25519PublicVerifier(pub)
    assert engine.verify_decision(signed, verifier)


def test_public_key_verify_grant(tmp_path):
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
    signed = engine.sign_grant(grant, Ed25519Signer(key))
    verifier = Ed25519PublicVerifier(pub)
    assert engine.verify_grant(signed, verifier)


def test_wrong_public_key_fails(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    other_pub = tmp_path / "other.pub"
    Ed25519Signer.generate_keypair(key, pub)
    Ed25519Signer.generate_keypair(tmp_path / "other.pem", other_pub)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    assert not engine.verify_decision(signed, Ed25519PublicVerifier(other_pub))


def test_tampered_artifact_fails_public_verify(tmp_path):
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
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    signed["decision_hash"] = "sha256:" + "0" * 64
    assert not engine.verify_decision(signed, Ed25519PublicVerifier(pub))


def test_pcs_export_includes_public_key_ref(tmp_path):
    from adapters.pcs.export_artifact import export_pcs_artifact

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
    signed_dec = engine.sign_decision(decision, Ed25519Signer(key))
    grant = engine.issue_grant(packet, signed_dec)
    signed_grant = engine.sign_grant(grant, Ed25519Signer(key))
    out = export_pcs_artifact(packet, signed_dec, signed_grant, tmp_path / "pcs")
    import json

    manifest = json.loads((out / "release_manifest.json").read_text())
    assert manifest.get("reviewer_public_key_ref")
    assert "private" not in str(manifest).lower()
