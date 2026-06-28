"""Tests for minimal review queue (SCOPE-3)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from click.testing import CliRunner

from scope import ScopeEngine
from scope.cli import main
from scope.review_queue import ReviewQueue, queue_metrics

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


def test_review_queue_create_assign_status(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    queue_dir = tmp_path / "queues"
    out = tmp_path / "queue.json"

    entry = engine.create_review_queue(packet, queue_dir=queue_dir, sla_hours=48)
    entry.save(out)
    assert entry.status == "open"
    assert entry.queue_id.startswith("SCOPE-QUEUE-")

    engine.assign_review_queue(out, {"reviewer_id": "rev1", "role": "protocol_owner"})
    loaded = ReviewQueue.load(out)
    assert loaded.status == "assigned"
    assert loaded.status_summary()["reviewer"]["reviewer_id"] == "rev1"


def test_overdue_queue_detection(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, sla_hours=1, persist=False)
    entry._data["due_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out = tmp_path / f"{entry.queue_id}.json"
    entry.save(out)

    assert ReviewQueue.load(out).is_overdue()
    metrics = queue_metrics(tmp_path)
    assert metrics["open_queue_count"] == 1
    assert metrics["overdue_queue_count"] == 1


def test_quality_report_includes_queue_metrics(tmp_path):
    ledger = tmp_path / "events.jsonl"
    queue_dir = tmp_path / "queues"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = _sample_packet(engine)
    engine.create_review_queue(packet, queue_dir=queue_dir)
    report = engine.quality_report(queue_dir=queue_dir)
    assert report["metrics"]["open_queue_count"] == 1
    assert report["summary"]["overdue_queue_count"] == 0


def test_review_queue_status_transitions(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, persist=False)
    entry.save(out)
    assert entry.status == "open"

    engine.assign_review_queue(out, {"reviewer_id": "rev1", "role": "protocol_owner"})
    assert ReviewQueue.load(out).status == "assigned"

    engine.decide_review_queue(out, "SCOPE-DEC-TEST01")
    decided = ReviewQueue.load(out)
    assert decided.status == "decided"
    assert decided.status_summary()["decision_id"] == "SCOPE-DEC-TEST01"

    engine.grant_review_queue(out, "SCOPE-GRANT-TEST01")
    granted = ReviewQueue.load(out)
    assert granted.status == "granted"
    assert granted.status_summary()["grant_id"] == "SCOPE-GRANT-TEST01"
    assert not granted.is_overdue()


def test_review_queue_close_from_assigned(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    out = tmp_path / "queue.json"
    entry = ReviewQueue.create(packet, persist=False)
    entry.save(out)
    engine.assign_review_queue(out, {"reviewer_id": "rev1", "role": "protocol_owner"})
    engine.close_review_queue(out, reason="withdrawn")
    closed = ReviewQueue.load(out)
    assert closed.status == "closed"
    assert closed.to_artifact()["close_reason"] == "withdrawn"


def test_review_queue_list_command(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)
    queue_dir = tmp_path / "queues"
    engine.create_review_queue(packet, queue_dir=queue_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "review",
            "queue",
            "list",
            "--queue-dir",
            str(queue_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.output)
    assert body["open_queue_count"] == 1
    assert len(body["entries"]) == 1

