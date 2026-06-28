"""Tests for workflow SLA escalation."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scope import ScopeEngine
from scope.review_queue import ReviewQueue
from scope.workflow_escalation import scan_overdue_queues


def test_scan_overdue_queues_dry_run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = ScopeEngine.from_policy_dir("policy/")
        packet = engine.create_packet(
            {"record_id": "R-OVER", "scientific_action_type": "A6_experimental_planning"},
            {
                "akta_admissibility": "review_required",
                "scientific_action_type": "A6_experimental_planning",
                "requested_action": "plan_validation",
                "requested_tool": "experiment_planner.create_validation_plan",
                "requested_scope": "single_validation_plan",
            },
        )
        entry = ReviewQueue.create(packet, sla_hours=1, queue_dir=tmp, persist=True)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0)
        entry._data["due_at"] = past.isoformat().replace("+00:00", "Z")
        entry.save(Path(tmp) / f"{entry.queue_id}.json")
        results = scan_overdue_queues(tmp, "policy/", dry_run=True)
        assert len(results) >= 1
        assert results[0]["overdue"] is True
