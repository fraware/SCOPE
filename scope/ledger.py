"""Hash-chained JSONL ledger for SCOPE events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scope.errors import LedgerError
from scope.hash import attach_hash, verify_hash


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_event_id() -> str:
    return f"SCOPE-EVT-{uuid.uuid4().hex[:8].upper()}"


class ScopeLedger:
    """Append-only hash-chained JSONL ledger."""

    GENESIS_HASH = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._events: list[dict[str, Any]] = []
        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        assert self.path is not None
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self._events.append(json.loads(line))
        self._verify_chain()

    def _verify_chain(self) -> None:
        prev = self.GENESIS_HASH
        for event in self._events:
            if event.get("previous_event_hash") != prev:
                raise LedgerError("Ledger hash chain broken")
            if not verify_hash(event, "event_hash"):
                raise LedgerError(f"Invalid event hash: {event.get('event_id')}")
            prev = event["event_hash"]

    @property
    def last_hash(self) -> str:
        if not self._events:
            return self.GENESIS_HASH
        return str(self._events[-1]["event_hash"])

    def append(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        packet_id: str | None = None,
        decision_id: str | None = None,
        grant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "event_id": _new_event_id(),
            "timestamp": _utc_now(),
            "event_type": event_type,
            "previous_event_hash": self.last_hash,
        }
        if actor_id:
            event["actor_id"] = actor_id
        if packet_id:
            event["packet_id"] = packet_id
        if decision_id:
            event["decision_id"] = decision_id
        if grant_id:
            event["grant_id"] = grant_id
        if metadata:
            event["metadata"] = metadata
        event = attach_hash(event, "event_hash")
        self._events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for event in self._events:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
