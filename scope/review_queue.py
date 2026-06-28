"""Minimal review queue for open, assigned, and overdue tracking."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scope._version import __version__
from scope.errors import ScopeValidationError
from scope.schema_util import validate_artifact

DEFAULT_QUEUE_DIR = Path(".scope/queues")
DEFAULT_SLA_HOURS = 72
OPEN_STATUSES = frozenset({"open", "assigned"})
TERMINAL_STATUSES = frozenset({"granted", "closed", "cancelled", "completed"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _new_queue_id() -> str:
    return f"SCOPE-QUEUE-{uuid.uuid4().hex[:6].upper()}"


class ReviewQueue:
    """Single review queue entry backed by a JSON artifact."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def create(
        cls,
        packet: dict[str, Any],
        *,
        sla_hours: int = DEFAULT_SLA_HOURS,
        queue_dir: str | Path | None = None,
        persist: bool = True,
    ) -> ReviewQueue:
        created = _utc_now()
        due = (_parse_ts(created) + timedelta(hours=sla_hours)).replace(microsecond=0)
        due_at = due.isoformat().replace("+00:00", "Z")
        artifact: dict[str, Any] = {
            "queue_id": _new_queue_id(),
            "queue_version": __version__,
            "packet_id": packet["packet_id"],
            "status": "open",
            "created_at": created,
            "due_at": due_at,
            "sla_hours": sla_hours,
            "packet_snapshot": {
                "packet_id": packet["packet_id"],
                "scientific_action_type": packet["review_request"]["scientific_action_type"],
                "requested_tool": packet["review_request"]["requested_tool"],
                "akta_admissibility": packet["review_request"].get("akta_admissibility"),
            },
        }
        queue = cls(artifact)
        queue.validate()
        if persist:
            target_dir = Path(queue_dir) if queue_dir else DEFAULT_QUEUE_DIR
            queue.save(target_dir / f"{artifact['queue_id']}.json")
        return queue

    @classmethod
    def load(cls, path: str | Path) -> ReviewQueue:
        with Path(path).open(encoding="utf-8") as fh:
            data = json.load(fh)
        queue = cls(data)
        queue.validate()
        return queue

    @property
    def queue_id(self) -> str:
        return str(self._data["queue_id"])

    @property
    def status(self) -> str:
        return str(self._data["status"])

    def to_artifact(self) -> dict[str, Any]:
        return dict(self._data)

    def validate(self) -> None:
        validate_artifact(self._data, "scope_review_queue.schema.json")

    def save(self, path: str | Path | None = None) -> Path:
        if path is None:
            target = DEFAULT_QUEUE_DIR / f"{self.queue_id}.json"
        else:
            target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return target

    def assign(self, reviewer: dict[str, Any]) -> None:
        if self.status not in OPEN_STATUSES:
            raise ScopeValidationError(
                f"Cannot assign reviewer to queue entry in status {self.status}"
            )
        reviewer_id = reviewer.get("reviewer_id")
        role = reviewer.get("role")
        if not reviewer_id or not role:
            raise ScopeValidationError("Reviewer must include reviewer_id and role")
        self._data["status"] = "assigned"
        self._data["assigned_at"] = _utc_now()
        self._data["reviewer"] = {
            "reviewer_id": str(reviewer_id),
            "role": str(role),
        }
        self.validate()

    def mark_decided(self, decision_id: str) -> None:
        if self.status != "assigned":
            raise ScopeValidationError(
                f"Cannot mark decided from queue status {self.status}; expected assigned"
            )
        self._data["status"] = "decided"
        self._data["decided_at"] = _utc_now()
        self._data["decision_id"] = str(decision_id)
        self.validate()

    def mark_granted(self, grant_id: str) -> None:
        if self.status != "decided":
            raise ScopeValidationError(
                f"Cannot mark granted from queue status {self.status}; expected decided"
            )
        self._data["status"] = "granted"
        self._data["granted_at"] = _utc_now()
        self._data["grant_id"] = str(grant_id)
        self.validate()

    def close(self, *, reason: str = "") -> None:
        if self.status in TERMINAL_STATUSES:
            raise ScopeValidationError(f"Cannot close queue entry in status {self.status}")
        self._data["status"] = "closed"
        self._data["closed_at"] = _utc_now()
        if reason:
            self._data["close_reason"] = reason
        self.validate()

    def complete(self) -> None:
        """Backward-compatible alias: close without grant."""
        self.close(reason="completed_without_grant")

    def is_overdue(self, *, now: datetime | None = None) -> bool:
        if self.status not in OPEN_STATUSES:
            return False
        current = now or datetime.now(timezone.utc)
        return current > _parse_ts(str(self._data["due_at"]))

    def status_summary(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "packet_id": self._data["packet_id"],
            "status": self.status,
            "created_at": self._data["created_at"],
            "due_at": self._data["due_at"],
            "assigned_at": self._data.get("assigned_at"),
            "decided_at": self._data.get("decided_at"),
            "granted_at": self._data.get("granted_at"),
            "closed_at": self._data.get("closed_at"),
            "overdue": self.is_overdue(),
            "reviewer": self._data.get("reviewer"),
            "decision_id": self._data.get("decision_id"),
            "grant_id": self._data.get("grant_id"),
        }


def list_queue_files(queue_dir: str | Path | None = None) -> list[Path]:
    root = Path(queue_dir) if queue_dir else DEFAULT_QUEUE_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob("SCOPE-QUEUE-*.json"))


def load_all_queues(queue_dir: str | Path | None = None) -> list[ReviewQueue]:
    return [ReviewQueue.load(path) for path in list_queue_files(queue_dir)]


def queue_metrics(queue_dir: str | Path | None = None) -> dict[str, int]:
    """Count open and overdue queue entries on disk."""
    open_count = 0
    overdue_count = 0
    for queue in load_all_queues(queue_dir):
        if queue.status in OPEN_STATUSES:
            open_count += 1
            if queue.is_overdue():
                overdue_count += 1
    return {"open_queue_count": open_count, "overdue_queue_count": overdue_count}


def aggregate_queue_status(queue_dir: str | Path | None = None) -> dict[str, Any]:
    queues = load_all_queues(queue_dir)
    metrics = queue_metrics(queue_dir)
    return {
        "queue_dir": str(Path(queue_dir) if queue_dir else DEFAULT_QUEUE_DIR),
        "entries": [queue.status_summary() for queue in queues],
        **metrics,
    }
