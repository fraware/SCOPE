"""Pluggable notification sinks for workflow escalation."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class NotificationSink(ABC):
    """Deliver workflow escalation or SLA breach notifications."""

    @abstractmethod
    def notify(self, event: dict[str, Any]) -> None:
        """Send notification payload."""


class LogSink(NotificationSink):
    """Default sink: structured log output."""

    def notify(self, event: dict[str, Any]) -> None:
        logger.info("SCOPE notification: %s", json.dumps(event, sort_keys=True))


class WebhookSink(NotificationSink):
    """POST JSON payloads to a webhook URL."""

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

    def notify(self, event: dict[str, Any]) -> None:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(event, sort_keys=True).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            if resp.status >= 400:
                raise urllib.error.URLError(f"Webhook returned HTTP {resp.status}")


class EmailSink(NotificationSink):
    """
    Email notification interface.

    Production deployments wire SMTP or institutional mail APIs at this boundary.
    """

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        from_addr: str | None = None,
        to_addrs: list[str] | None = None,
    ) -> None:
        self.smtp_host = smtp_host or os.environ.get("SCOPE_SMTP_HOST")
        self.smtp_port = smtp_port
        self.from_addr = from_addr or os.environ.get("SCOPE_SMTP_FROM")
        self.to_addrs = to_addrs or []

    def notify(self, event: dict[str, Any]) -> None:
        if not self.smtp_host or not self.from_addr or not self.to_addrs:
            raise ValueError(
                "EmailSink requires SCOPE_SMTP_HOST, SCOPE_SMTP_FROM, and recipient addresses"
            )
        logger.info(
            "Email notification queued to %s: %s",
            self.to_addrs,
            event.get("event_type", "workflow"),
        )


def resolve_notification_sinks(
    policy_dir: str | os.PathLike[str] | None = None,
) -> list[NotificationSink]:
    """Build notification sinks from policy and environment."""
    sinks: list[NotificationSink] = [LogSink()]
    webhook = os.environ.get("SCOPE_NOTIFY_WEBHOOK_URL")
    if webhook:
        token = os.environ.get("SCOPE_NOTIFY_WEBHOOK_TOKEN")
        sinks.append(WebhookSink(webhook, token=token))
    else:
        try:
            from pathlib import Path

            import yaml

            if policy_dir:
                path = Path(policy_dir) / "workflow_escalation.yaml"
                if path.is_file():
                    with path.open(encoding="utf-8") as fh:
                        cfg = yaml.safe_load(fh) or {}
                    url = cfg.get("notify_webhook_url")
                    if url:
                        sinks.append(WebhookSink(str(url)))
        except Exception:
            pass
    return sinks


def emit_notification(event: dict[str, Any], sinks: list[NotificationSink] | None = None) -> None:
    """Fan-out notification to configured sinks."""
    targets = sinks or resolve_notification_sinks()
    for sink in targets:
        try:
            sink.notify(event)
        except Exception as exc:
            logger.warning("Notification sink %s failed: %s", type(sink).__name__, exc)
