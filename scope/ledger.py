"""Hash-chained JSONL ledger for SCOPE events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scope.errors import LedgerError
from scope.hash import attach_hash, verify_hash
from scope.ledger_sinks import LedgerSink, LocalJsonlSink, MultiSink, build_ledger_sinks


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_event_id() -> str:
    return f"SCOPE-EVT-{uuid.uuid4().hex[:8].upper()}"


class ScopeLedger:
    """Append-only hash-chained JSONL ledger."""

    GENESIS_HASH = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        sinks: list[LedgerSink] | None = None,
    ) -> None:
        self.path = Path(path) if path else None
        self._events: list[dict[str, Any]] = []
        if sinks is not None:
            self._sinks = sinks
        elif self.path:
            self._sinks = build_ledger_sinks(self.path)
        else:
            self._sinks = []
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
        reviewer_role: str | None = None,
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
        if reviewer_role:
            event["reviewer_role"] = reviewer_role
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
        if self._sinks:
            MultiSink(self._sinks).append(event)
        elif self.path:
            LocalJsonlSink(self.path).append(event)
        return event

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def events_for_grant(self, grant_id: str) -> list[dict[str, Any]]:
        return [e for e in self._events if e.get("grant_id") == grant_id]

    def grant_used(self, grant_id: str) -> bool:
        """Return True if ledger records prior grant_used for this grant."""
        return any(e.get("event_type") == "grant_used" for e in self.events_for_grant(grant_id))

    def grant_revoked(self, grant_id: str) -> bool:
        return any(e.get("event_type") == "grant_revoked" for e in self.events_for_grant(grant_id))

    def grant_status(self, grant_id: str) -> dict[str, Any]:
        events = self.events_for_grant(grant_id)
        used = self.grant_used(grant_id)
        revoked = self.grant_revoked(grant_id)
        expired = any(e.get("event_type") == "grant_expired" for e in events)
        status = "active"
        reason = None
        if revoked:
            status = "revoked"
            rev = next(e for e in events if e.get("event_type") == "grant_revoked")
            reason = (rev.get("metadata") or {}).get("reason", "Grant revoked")
        elif expired:
            status = "expired"
            exp = next(e for e in events if e.get("event_type") == "grant_expired")
            reason = (exp.get("metadata") or {}).get("reason", "Grant expired")
        elif used:
            status = "consumed"
            reason = "Single-use grant already consumed per ledger"
        return {
            "grant_id": grant_id,
            "status": status,
            "used": used,
            "revoked": revoked,
            "expired": expired,
            "reason": reason,
            "event_count": len(events),
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for event in self._events:
                fh.write(json.dumps(event, sort_keys=True) + "\n")
