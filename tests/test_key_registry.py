"""Tests for reviewer key registry workflow (SCOPE-4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from scope import ScopeEngine
from scope.errors import ScopeValidationError
from scope.key_registry import register_reviewer_key, verify_decision_against_registry
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent


def test_key_register_and_verify_registry(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    result = register_reviewer_key(policy_copy, "rev1", pub, private_key_path=key)
    assert result["reviewer_id"] == "rev1"
    registry = yaml.safe_load((policy_copy / "reviewer_key_registry.yaml").read_text())
    assert registry["reviewers"]["rev1"]["public_key_ref"] == result["public_key_ref"]

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-KEY", "scientific_action_type": "A5_protocol_modification"}
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
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    verify = verify_decision_against_registry(signed, policy_copy)
    assert verify["binding_valid"] is True
    assert verify["signature_valid"] is True


def test_sign_rejects_unregistered_signer(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    good_key = tmp_path / "good.pem"
    good_pub = tmp_path / "good.pub"
    Ed25519Signer.generate_keypair(good_key, good_pub)
    register_reviewer_key(policy_copy, "rev1", good_pub)

    wrong_key = tmp_path / "wrong.pem"
    wrong_pub = tmp_path / "wrong.pub"
    Ed25519Signer.generate_keypair(wrong_key, wrong_pub)

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-KEY2", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "retry",
        },
    )
    with pytest.raises(ScopeValidationError, match="registry"):
        engine.sign_decision(decision, Ed25519Signer(wrong_key))


def test_verify_registry_resolves_public_key_from_registry(tmp_path):
    """verify-registry uses registry public_key_file; no manual public key path."""
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_copy, "rev1", pub, private_key_path=key)

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-KEY3", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    signed = engine.sign_decision(
        engine.submit_decision(
            packet,
            {"reviewer_id": "rev1", "role": "protocol_owner"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "protocol_draft",
                "rationale": "ok",
            },
        ),
        Ed25519Signer(key),
    )
    verify = verify_decision_against_registry(signed, policy_copy)
    assert verify["signature_valid"] is True
    assert verify["registry_hash"].startswith("sha256:")


def test_decision_and_grant_provenance_include_registry_hash(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_copy, "rev1", pub, private_key_path=key)

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-PROV", "scientific_action_type": "A5_protocol_modification"}
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
    assert decision["provenance"]["reviewer_key_registry_hash"].startswith("sha256:")
    signed = engine.sign_decision(decision, Ed25519Signer(key))
    grant = engine.issue_grant(packet, signed)
    assert grant["provenance"]["reviewer_key_registry_hash"].startswith("sha256:")


def test_key_list_registry(tmp_path):
    from scope.key_registry import list_registry_reviewers, verify_registry_integrity

    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    pub = tmp_path / "reviewer.pub"
    key = tmp_path / "reviewer.pem"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_copy, "rev1", pub)

    entries = list_registry_reviewers(policy_copy)
    assert len(entries) == 1
    assert entries[0]["reviewer_id"] == "rev1"

    summary = verify_registry_integrity(policy_copy)
    assert summary["reviewer_count"] == 1
    assert summary["registry_version"] == "scope-core-v0.5"


def test_pcs_export_includes_registry_metadata(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_copy, "rev1", pub, private_key_path=key)

    engine = ScopeEngine.from_policy_dir(policy_copy)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-PCS", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.sign_decision(
        engine.submit_decision(
            packet,
            {"reviewer_id": "rev1", "role": "protocol_owner"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "protocol_draft",
                "rationale": "ok",
            },
        ),
        Ed25519Signer(key),
    )
    grant = engine.issue_grant(packet, decision)

    from adapters.pcs.export_artifact import export_pcs_artifact

    out = tmp_path / "pcs"
    export_pcs_artifact(
        packet,
        decision,
        grant,
        out,
        registry_version=engine.policy.reviewer_key_registry_version,
        registry_hash=engine.policy.reviewer_key_registry_hash,
    )
    manifest = json.loads((out / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reviewer_public_key_ref"] == decision["reviewer_public_key_ref"]
    assert manifest["registry_version"]
    assert manifest["registry_hash"].startswith("sha256:")
