"""Tests for ledger sinks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scope.ledger_sinks import LocalJsonlSink, MultiSink, RemoteHttpSink


def test_local_jsonl_sink_appends() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        sink = LocalJsonlSink(path)
        sink.append({"event_id": "E1", "event_type": "test"})
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event_id"] == "E1"


def test_remote_sink_logs_failure() -> None:
    sink = RemoteHttpSink("http://127.0.0.1:1/unreachable")
    with patch("scope.ledger_sinks.logger.warning") as warn:
        sink.append({"event_id": "E2"})
        assert warn.called


def test_multi_sink_fanout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        sinks = [LocalJsonlSink(path), RemoteHttpSink("http://127.0.0.1:1/unreachable")]
        with patch("scope.ledger_sinks.logger.warning"):
            MultiSink(sinks).append({"event_id": "E3"})
        assert "E3" in path.read_text(encoding="utf-8")
