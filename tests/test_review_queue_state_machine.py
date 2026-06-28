"""Tests for review queue workflow state machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import ScopeValidationError
from scope.review_queue import ReviewQueue
from scope.review_workflow import validate_transition

ROOT = Path(__file__).resolve().parent.parent


def _sample_packet(engine: ScopeEngine) -> dict:
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-RQ", "scientific_action_type": "A5_protocol_modification"}
    return engine.create_packet(record, trigger)


def test_forbidden_open_to_granted() -> None:
    with pytest.raises(ScopeValidationError, match="Invalid"):
        validate_transition("open", "granted")


def test_forbidden_assigned_to_granted() -> None:
    with pytest.raises(ScopeValidationError, match="Invalid"):
        validate_transition("assigned", "granted")


def test_forbidden_needs_information_to_granted() -> None:
    with pytest.raises(ScopeValidationError, match="Invalid"):
        validate_transition("needs_information", "granted")


def test_forbidden_needs_information_to_decided() -> None:
    with pytest.raises(ScopeValidationError, match="Invalid"):
        validate_transition("needs_information", "decided")


def test_information_received_workflow(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    entry = ReviewQueue.create(packet, persist=False)
    entry.assign({"reviewer_id": "rev1", "role": "protocol_owner"})
    entry.mark_in_review()
    entry.mark_needs_information(reason="missing data")
    entry.mark_information_received()
    assert entry.status == "in_review"
    entry.mark_decided("SCOPE-DEC-IR")
    entry.mark_granted("SCOPE-GRANT-IR")
    entry.save(tmp_path / "queue.json")


def test_escalation_records_reason_and_actor(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    packet = _sample_packet(engine)
    entry = ReviewQueue.create(packet, persist=False)
    entry.assign({"reviewer_id": "rev1", "role": "protocol_owner"})
    entry.mark_escalated(
        {"reviewer_id": "lead1", "role": "lab_operations_lead"},
        reason="SLA breach",
        actor_id="system",
    )
    assert entry.status == "escalated"
    assert entry.to_artifact()["escalation_reason"] == "SLA breach"
    assert entry.to_artifact()["escalation_actor_id"] == "system"


def test_escalation_emits_ledger_event(tmp_path: Path) -> None:
    ledger_path = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger_path)
    packet = _sample_packet(engine)
    queue_path = tmp_path / "queue.json"
    entry = engine.create_review_queue(packet, queue_dir=tmp_path)
    entry.save(queue_path)
    entry.assign({"reviewer_id": "rev1", "role": "protocol_owner"})
    entry.save(queue_path)

    engine.escalate_review_queue_entry(
        queue_path,
        {"reviewer_id": "lead1", "role": "lab_operations_lead"},
        reason="SLA breach",
        actor_id="ops-bot",
    )

    events = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    escalations = [
        json.loads(line)
        for line in events
        if json.loads(line).get("event_type") == "review_queue_escalated"
    ]
    assert len(escalations) == 1
    metadata = escalations[0]["metadata"]
    assert metadata["escalation_reason"] == "SLA breach"
    assert escalations[0]["actor_id"] == "ops-bot"


def test_happy_path_workflow(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, persist=False)
    entry.save(out)

    entry = ReviewQueue.load(out)
    entry.assign({"reviewer_id": "rev1", "role": "protocol_owner"})
    entry.mark_in_review()
    entry.mark_decided("SCOPE-DEC-WF01")
    entry.mark_granted("SCOPE-GRANT-WF01")
    entry.save(out)

    final = ReviewQueue.load(out)
    assert final.status == "granted"


def test_expired_requires_reopen_before_grant(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, persist=False)
    entry.expire()
    entry.save(out)

    loaded = ReviewQueue.load(out)
    with pytest.raises(ScopeValidationError, match="expired"):
        loaded.mark_granted("SCOPE-GRANT-EX")


def test_reopen_from_expired(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, persist=False)
    entry.expire()
    entry.reopen()
    assert entry.status == "open"
    entry.save(out)


def test_needs_information_blocks_decided(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    entry = ReviewQueue.create(packet, persist=False)
    entry.assign({"reviewer_id": "rev1", "role": "protocol_owner"})
    entry.mark_in_review()
    entry.mark_needs_information(reason="missing data")
    with pytest.raises(ScopeValidationError, match="needs_information"):
        entry.mark_decided("SCOPE-DEC-NI")
