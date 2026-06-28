"""Tests for signing identity binding."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import ScopeValidationError
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent


def test_sign_attaches_reviewer_public_key_ref(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    signer = Ed25519Signer(key)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-SIGN", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    signed = engine.sign_decision(decision, signer)
    assert signed["reviewer_public_key_ref"] == signer.public_key_ref()
    assert signed["reviewer"]["reviewer_public_key_ref"] == signer.public_key_ref()


def test_sign_rejects_mismatched_reviewer_key_ref(tmp_path):
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    signer = Ed25519Signer(key)

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-SIGN2", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {
            "reviewer_id": "rev1",
            "role": "protocol_owner",
            "reviewer_public_key_ref": "sha256:deadbeef",
        },
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    with pytest.raises(ScopeValidationError, match="does not match"):
        engine.sign_decision(decision, signer)


def test_sign_enforces_reviewer_key_registry(tmp_path):
    import shutil

    import yaml

    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    expected_ref = Ed25519Signer.generate_keypair(key, pub)
    signer = Ed25519Signer(key)

    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    registry_path = policy_copy / "reviewer_key_registry.yaml"
    registry_path.write_text(
        yaml.dump(
            {
                "version": "scope-core-v0.6",
                "reviewers": {"rev1": expected_ref},
            }
        ),
        encoding="utf-8",
    )

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-REG", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    signed = engine.sign_decision(decision, signer)
    assert signed["reviewer_public_key_ref"] == expected_ref

    wrong_key = tmp_path / "wrong.pem"
    wrong_pub = tmp_path / "wrong.pub"
    Ed25519Signer.generate_keypair(wrong_key, wrong_pub)
    decision2 = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "retry",
        },
    )
    with pytest.raises(ScopeValidationError, match="registry"):
        engine.sign_decision(decision2, Ed25519Signer(wrong_key))
