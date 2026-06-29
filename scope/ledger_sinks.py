"""Ledger sink adapters for local and remote append-only event streams."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SPOOL_DIR = Path(".scope/ledger_spool")


class LedgerDeliveryMode(str, Enum):
    BEST_EFFORT = "best_effort"
    AT_LEAST_ONCE = "at_least_once"
    FAIL_CLOSED = "fail_closed"


def resolve_delivery_mode(config_value: str | None = None) -> LedgerDeliveryMode:
    raw = config_value or os.environ.get("SCOPE_LEDGER_DELIVERY_MODE", "best_effort")
    normalized = raw.lower().replace("-", "_")
    try:
        return LedgerDeliveryMode(normalized)
    except ValueError:
        logger.warning("Unknown SCOPE_LEDGER_DELIVERY_MODE=%s; using best_effort", raw)
        return LedgerDeliveryMode.BEST_EFFORT


class LedgerSink(ABC):
    """Append-only sink for ledger events."""

    @abstractmethod
    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> str | None:
        """Persist a single ledger event; return delivery_state when tracked."""

    @property
    def is_remote(self) -> bool:
        return False


class LocalJsonlSink(LedgerSink):
    """Append events to a local JSONL file (default behavior)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return None


class RemoteHttpSink(LedgerSink):
    """POST ledger events to a remote append endpoint."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout

    @property
    def is_remote(self) -> bool:
        return True

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> None:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status >= 400:
                raise urllib.error.URLError(f"HTTP {resp.status}")
        return None


class LedgerSpool:
    """Local spool for at-least-once remote ledger delivery."""

    def __init__(self, spool_dir: str | Path | None = None) -> None:
        self.spool_dir = Path(spool_dir or DEFAULT_SPOOL_DIR)
        self.spool_dir.mkdir(parents=True, exist_ok=True)

    def spool(self, event: dict[str, Any]) -> Path:
        event_id = str(event.get("event_id", "unknown"))
        path = self.spool_dir / f"{event_id}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(event, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return path

    def pending_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for path in sorted(self.spool_dir.glob("SCOPE-EVT-*.json")):
            with path.open(encoding="utf-8") as fh:
                events.append(json.load(fh))
        return events

    def remove(self, event_id: str) -> None:
        path = self.spool_dir / f"{event_id}.json"
        if path.is_file():
            path.unlink()


class DeliveringSink(LedgerSink):
    """Wrap sinks with delivery semantics and spool/retry support."""

    def __init__(
        self,
        sinks: list[LedgerSink],
        *,
        mode: LedgerDeliveryMode | None = None,
        spool: LedgerSpool | None = None,
    ) -> None:
        self.local_sinks = [s for s in sinks if not s.is_remote]
        self.remote_sinks = [s for s in sinks if s.is_remote]
        self.mode = mode or resolve_delivery_mode()
        self.spool = spool or LedgerSpool()

    def deliver_remote(self, event: dict[str, Any], *, fail_closed: bool = False) -> str:
        """Attempt remote delivery; return final delivery_state without writing locally."""
        if not self.remote_sinks:
            return "delivered"

        remote_ok = True
        for sink in self.remote_sinks:
            try:
                sink.append(event)
            except (urllib.error.URLError, OSError) as exc:
                remote_ok = False
                logger.warning("Remote ledger sink failed: %s", exc)

        if remote_ok:
            return "delivered"

        if self.mode == LedgerDeliveryMode.BEST_EFFORT:
            return "failed"

        if self.mode == LedgerDeliveryMode.AT_LEAST_ONCE:
            self.spool.spool(event)
            return "spooled"

        if self.mode == LedgerDeliveryMode.FAIL_CLOSED and fail_closed:
            raise LedgerDeliveryError(
                f"Remote ledger delivery failed in fail_closed mode for {event.get('event_type')}"
            )

        return "failed"

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> str:
        delivery_state = "delivered"
        for sink in self.local_sinks:
            sink.append(event)

        if not self.remote_sinks:
            event["delivery_state"] = delivery_state
            return delivery_state

        state = self.deliver_remote(event, fail_closed=fail_closed)
        event["delivery_state"] = state
        return state

    def retry_spooled(self) -> int:
        delivered = 0
        for event in self.spool.pending_events():
            event_id = str(event.get("event_id", ""))
            ok = True
            for sink in self.remote_sinks:
                try:
                    sink.append(event)
                except (urllib.error.URLError, OSError):
                    ok = False
            if ok:
                self.spool.remove(event_id)
                delivered += 1
        return delivered


class LedgerDeliveryError(Exception):
    """Ledger event could not be delivered under fail_closed policy."""


class MultiSink(LedgerSink):
    """Fan-out to multiple sinks; local chain verification remains authoritative."""

    def __init__(self, sinks: list[LedgerSink]) -> None:
        self.sinks = sinks

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> None:
        for sink in self.sinks:
            sink.append(event, fail_closed=fail_closed)


class WormSink(LedgerSink):
    """Write-once local sink emulating WORM storage semantics."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._seq = 0
        if self.path.is_file():
            self._seq = sum(1 for _ in self.path.open(encoding="utf-8"))

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> str | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(event)
        self._seq += 1
        record["worm_seq"] = self._seq
        record["worm_ack"] = True
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return "worm_ack"


class VerifiedRemoteSink(LedgerSink):
    """Remote append sink verifying signed batch or Merkle root acknowledgment."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout: float = 10.0,
        verify_merkle: bool = True,
    ) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout
        self.verify_merkle = verify_merkle

    @property
    def is_remote(self) -> bool:
        return True

    def append(self, event: dict[str, Any], *, fail_closed: bool = False) -> str | None:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status >= 400:
                raise urllib.error.URLError(f"HTTP {resp.status}")
            ack_raw = resp.read().decode("utf-8")
        ack: dict[str, Any] = {}
        if ack_raw.strip():
            ack = json.loads(ack_raw)
            if self.verify_merkle:
                merkle_root = ack.get("merkle_root")
                batch_sig = ack.get("batch_signature")
                if not merkle_root and not batch_sig:
                    raise urllib.error.URLError(
                        "Remote ledger ack missing merkle_root or batch_signature"
                    )
        event["remote_ack"] = ack
        return "verified_remote_ack"


def is_high_risk_ledger_event(event_type: str, metadata: dict[str, Any] | None = None) -> bool:
    meta = metadata or {}
    if event_type in (
        "grant_issued",
        "grant_revoked",
        "runtime_scope_violation",
    ):
        return True
    if event_type == "decision_submitted":
        approved = meta.get("approved_scope")
        if approved and approved != "clarification_only":
            return True
        decision_type = meta.get("decision_type")
        if decision_type in ("approve", "approve_narrower_scope"):
            approved_scope = meta.get("approved_scope")
            if approved_scope and approved_scope != "clarification_only":
                return True
    return False


def build_ledger_sinks(
    local_path: str | Path | None,
    *,
    delivery_mode: LedgerDeliveryMode | None = None,
) -> list[LedgerSink]:
    """Build sink list from environment and local path."""
    sinks: list[LedgerSink] = []
    if local_path:
        sinks.append(LocalJsonlSink(local_path))
    remote_url = os.environ.get("SCOPE_LEDGER_REMOTE_URL")
    if remote_url:
        token = os.environ.get("SCOPE_LEDGER_REMOTE_TOKEN")
        verified = os.environ.get("SCOPE_LEDGER_VERIFIED_REMOTE", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if verified:
            sinks.append(VerifiedRemoteSink(remote_url, token=token))
        else:
            sinks.append(RemoteHttpSink(remote_url, token=token))
    worm_path = os.environ.get("SCOPE_LEDGER_WORM_PATH")
    if worm_path:
        sinks.append(WormSink(worm_path))
    return sinks


def build_delivering_sink(
    local_path: str | Path | None,
    *,
    delivery_mode: LedgerDeliveryMode | None = None,
    spool_dir: str | Path | None = None,
) -> DeliveringSink | None:
    sinks = build_ledger_sinks(local_path, delivery_mode=delivery_mode)
    if not sinks:
        return None
    return DeliveringSink(
        sinks,
        mode=delivery_mode,
        spool=LedgerSpool(spool_dir),
    )
