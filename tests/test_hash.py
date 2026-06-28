"""Tests for canonical SHA256 hashing."""

import copy

from scope.hash import (
    attach_hash,
    canonical_json,
    compute_hash,
    strip_hash_fields,
    verify_hash,
)


def test_canonical_json_is_deterministic():
    data = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    assert canonical_json(data) == canonical_json(copy.deepcopy(data))
    assert canonical_json(data) == '{"a":1,"b":2,"nested":{"y":8,"z":9}}'


def test_strip_hash_fields():
    data = {
        "packet_id": "PKT-1",
        "packet_hash": "sha256:abc",
        "decision_hash": "sha256:def",
        "event_hash": "sha256:ghi",
    }
    stripped = strip_hash_fields(data)
    assert stripped == {"packet_id": "PKT-1"}


def test_compute_hash_excludes_own_hash_field():
    payload = {"packet_id": "PKT-1", "packet_version": "0.1"}
    h1 = compute_hash(payload, field_name="packet_hash")
    h2 = compute_hash({**payload, "packet_hash": h1}, field_name="packet_hash")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_attach_and_verify_hash():
    artifact = {"decision_id": "DEC-1", "decision": {"type": "reject"}}
    signed = attach_hash(artifact, "decision_hash")
    assert verify_hash(signed, "decision_hash")
    tampered = dict(signed, decision_id="DEC-2")
    assert not verify_hash(tampered, "decision_hash")


def test_hash_changes_when_payload_changes():
    base = {"grant_id": "GRANT-1", "authorization": {"approved_scope": "protocol_draft"}}
    h1 = compute_hash(base, field_name="grant_hash")
    h2 = compute_hash(
        {**base, "authorization": {"approved_scope": "active_protocol_update"}},
        field_name="grant_hash",
    )
    assert h1 != h2


def test_scope_trust_root_hash():
    from scope.hash import scope_trust_root_hash

    policy_hash = "sha256:" + "a" * 64
    registry_hash = "sha256:" + "b" * 64
    root = scope_trust_root_hash(policy_hash, registry_hash)
    assert root.startswith("sha256:")
    assert len(root) == 7 + 64
