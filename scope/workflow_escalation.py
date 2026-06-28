"""SLA escalation scanning for overdue review queues."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scope.review_queue import OPEN_STATUSES, load_all_queues


def load_escalation_policy(policy_dir: str | Path) -> dict[str, Any]:
    path = Path(policy_dir) / "workflow_escalation.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def scan_overdue_queues(
    queue_dir: str | Path | None,
    policy_dir: str | Path,
    *,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Find overdue queue entries and optionally escalate."""
    escalation = load_escalation_policy(policy_dir)
    escalation_reviewer = escalation.get("escalation_reviewer") or {}
    auto_escalate = bool(escalation.get("auto_escalate_status", True))
    results: list[dict[str, Any]] = []

    for queue in load_all_queues(queue_dir):
        if queue.status not in OPEN_STATUSES or not queue.is_overdue():
            continue
        summary = queue.status_summary()
        action: dict[str, Any] = {
            "queue_id": queue.queue_id,
            "packet_id": summary["packet_id"],
            "status": summary["status"],
            "due_at": summary["due_at"],
            "overdue": True,
            "dry_run": dry_run,
            "escalated": False,
        }
        if not dry_run and auto_escalate and escalation_reviewer:
            queue._data["escalated"] = True
            queue._data["escalation_reviewer"] = dict(escalation_reviewer)
            if queue.status == "open":
                queue.assign(escalation_reviewer)
            queue.save()
            action["escalated"] = True
            action["escalation_reviewer"] = escalation_reviewer
        results.append(action)
    return results


def emit_sla_breach_events(
    engine: Any,
    breaches: list[dict[str, Any]],
    *,
    policy_dir: str | Path,
) -> list[dict[str, Any]]:
    """Append review_sla_breached ledger events for each breach."""
    escalation = load_escalation_policy(policy_dir)
    if not escalation.get("emit_ledger_events", True):
        return []
    events: list[dict[str, Any]] = []
    for breach in breaches:
        event = engine.ledger.append(
            "review_sla_breached",
            packet_id=breach.get("packet_id"),
            metadata={
                "queue_id": breach.get("queue_id"),
                "due_at": breach.get("due_at"),
                "escalated": breach.get("escalated", False),
                "escalation_reviewer": breach.get("escalation_reviewer"),
            },
        )
        events.append(event)
    return events
