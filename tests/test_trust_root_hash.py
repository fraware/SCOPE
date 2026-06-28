"""Tests for scope_trust_root_hash (v0.5.1)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scope import ScopeEngine
from scope.hash import combine_sha256_hashes, scope_trust_root_hash
from scope.key_registry import register_reviewer_key
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"


def test_combine_sha256_hashes_deterministic():
    h1 = "sha256:aaa111"
    h2 = "sha256:bbb222"
    assert combine_sha256_hashes(h1, h2) == combine_sha256_hashes(h1, h2)
    assert combine_sha256_hashes(h1, h2) != combine_sha256_hashes(h2, h1)


def test_scope_trust_root_from_policy():
    policy = ScopeEngine.from_policy_dir(ROOT / "policy").policy
    expected = scope_trust_root_hash(policy.policy_hash, policy.reviewer_key_registry_hash)
    assert policy.scope_trust_root_hash == expected


def test_decision_and_grant_include_trust_root():
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
    trust = engine.policy.scope_trust_root_hash
    assert decision["provenance"]["scope_trust_root_hash"] == trust
    grant = engine.issue_grant(packet, decision)
    assert grant["provenance"]["scope_trust_root_hash"] == trust


def test_trust_root_changes_when_registry_changes(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    engine1 = ScopeEngine.from_policy_dir(policy_copy)
    root1 = engine1.policy.scope_trust_root_hash

    pub = tmp_path / "reviewer.pub"
    key = tmp_path / "reviewer.pem"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_copy, "rev1", pub)

    engine2 = ScopeEngine.from_policy_dir(policy_copy)
    root2 = engine2.policy.scope_trust_root_hash
    assert root1 != root2


def test_pcs_export_includes_trust_root(tmp_path):
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
    assert manifest["scope_trust_root_hash"] == engine.policy.scope_trust_root_hash
