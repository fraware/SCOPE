"""Tests for WORM and verified remote ledger sinks."""

from __future__ import annotations

import json
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scope.ledger_sinks import VerifiedRemoteSink, WormSink


def test_worm_sink_append_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "worm.jsonl"
        sink = WormSink(path)
        sink.append({"event_id": "E1", "event_type": "test"})
        sink.append({"event_id": "E2", "event_type": "test"})
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        second = json.loads(lines[1])
        assert second["worm_seq"] == 2
        assert second["worm_ack"] is True


def test_verified_remote_requires_ack() -> None:
    sink = VerifiedRemoteSink("http://example.invalid/ledger")
    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        mock_open.return_value.__enter__.return_value = mock_resp
        with pytest.raises(urllib.error.URLError, match="merkle_root|batch_signature"):
            sink.append({"event_id": "E3", "event_type": "test"})
