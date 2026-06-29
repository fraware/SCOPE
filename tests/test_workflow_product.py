"""Tests for notifications and tenant queue isolation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scope.notifications import LogSink, WebhookSink, emit_notification
from scope.review_queue import resolve_queue_dir


def test_log_sink_notify(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    caplog.set_level(logging.INFO)
    sink = LogSink()
    sink.notify({"event_type": "test", "queue_id": "Q1"})
    assert "SCOPE notification" in caplog.text


def test_webhook_sink_posts() -> None:
    sink = WebhookSink("http://example.invalid/hook")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.status = 200
        sink.notify({"event_type": "review_sla_breached"})
        mock_open.assert_called_once()


def test_tenant_queue_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = resolve_queue_dir(tmp, tenant_id="lab-a")
        assert path.name == "lab-a"
        assert path.parent == Path(tmp)


def test_emit_notification_uses_log_sink() -> None:
    with patch.object(LogSink, "notify") as mock_notify:
        emit_notification({"event_type": "test"}, sinks=[LogSink()])
        mock_notify.assert_called_once()
