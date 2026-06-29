"""Minimal Jira ticket adapter for review queue sync."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, cast


def _jira_base() -> str:
    base = os.environ.get("SCOPE_JIRA_URL")
    if not base:
        raise ValueError("SCOPE_JIRA_URL not configured")
    return base.rstrip("/")


def _auth_header() -> dict[str, str]:
    token = os.environ.get("SCOPE_JIRA_TOKEN")
    if not token:
        raise ValueError("SCOPE_JIRA_TOKEN not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_ticket(queue_summary: dict[str, Any]) -> dict[str, Any]:
    """Create Jira issue from queue state."""
    project = os.environ.get("SCOPE_JIRA_PROJECT", "SCOPE")
    payload = {
        "fields": {
            "project": {"key": project},
            "summary": f"SCOPE review {queue_summary.get('queue_id')}",
            "description": json.dumps(queue_summary, indent=2),
            "issuetype": {"name": "Task"},
        }
    }
    req = urllib.request.Request(
        f"{_jira_base()}/rest/api/3/issue",
        data=json.dumps(payload).encode("utf-8"),
        headers=_auth_header(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))


def update_ticket(ticket_id: str, queue_summary: dict[str, Any]) -> dict[str, Any]:
    """Update existing Jira issue with queue state."""
    payload = {
        "fields": {
            "description": json.dumps(queue_summary, indent=2),
        }
    }
    req = urllib.request.Request(
        f"{_jira_base()}/rest/api/3/issue/{ticket_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_auth_header(),
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status == 204:
            return {"id": ticket_id, "updated": True}
        return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))
