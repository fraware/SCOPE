"""Ledger sink adapters for local and remote append-only event streams."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LedgerSink(ABC):
    """Append-only sink for ledger events."""

    @abstractmethod
    def append(self, event: dict[str, Any]) -> None:
        """Persist a single ledger event."""


class LocalJsonlSink(LedgerSink):
    """Append events to a local JSONL file (default behavior)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")


class RemoteHttpSink(LedgerSink):
    """Best-effort POST of ledger events to a remote append endpoint."""

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

    def append(self, event: dict[str, Any]) -> None:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status >= 400:
                    logger.warning("Remote ledger sink returned HTTP %s", resp.status)
        except urllib.error.URLError as exc:
            logger.warning("Remote ledger sink failed (best-effort): %s", exc)


class MultiSink(LedgerSink):
    """Fan-out to multiple sinks; local chain verification remains authoritative."""

    def __init__(self, sinks: list[LedgerSink]) -> None:
        self.sinks = sinks

    def append(self, event: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.append(event)


def build_ledger_sinks(local_path: str | Path | None) -> list[LedgerSink]:
    """Build sink list from environment and local path."""
    sinks: list[LedgerSink] = []
    if local_path:
        sinks.append(LocalJsonlSink(local_path))
    remote_url = os.environ.get("SCOPE_LEDGER_REMOTE_URL")
    if remote_url:
        token = os.environ.get("SCOPE_LEDGER_REMOTE_TOKEN")
        sinks.append(RemoteHttpSink(remote_url, token=token))
    return sinks
