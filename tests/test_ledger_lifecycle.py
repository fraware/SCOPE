"""Tests for review lifecycle ledger events."""

from __future__ import annotations

from pathlib import Path

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_review_assigned_on_packet_create(tmp_path):
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    events = engine.ledger.events()
    assigned = [e for e in events if e.get("event_type") == "review_assigned"]
    assert len(assigned) == 1
    meta = assigned[0]["metadata"]
    assert meta["packet_id"] == packet["packet_id"]
    assert "required_roles" in meta
    assert meta["quorum_mode"] in ("require_all", "require_any")


def test_review_opened_and_artifact_viewed(tmp_path):
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    packet_id = packet["packet_id"]

    opened = engine.open_review(packet_id, actor_id="reviewer-1")
    assert opened["event_type"] == "review_opened"
    assert opened["packet_id"] == packet_id

    viewed = engine.record_artifact_viewed(
        packet_id, "protocol_diff_ref", actor_id="reviewer-1"
    )
    assert viewed["event_type"] == "artifact_viewed"
    assert viewed["metadata"]["artifact_name"] == "protocol_diff_ref"

    report = engine.quality_report()
    counts = report["event_counts"]
    assert counts.get("review_opened", 0) >= 1
    assert counts.get("artifact_viewed", 0) >= 1
