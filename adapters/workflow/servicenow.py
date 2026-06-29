"""Minimal ServiceNow ticket adapter for review queue sync."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, cast


def _snow_base() -> str:
    base = os.environ.get("SCOPE_SERVICENOW_URL")
    if not base:
        raise ValueError("SCOPE_SERVICENOW_URL not configured")
    return base.rstrip("/")


def _auth_header() -> dict[str, str]:
    token = os.environ.get("SCOPE_SERVICENOW_TOKEN")
    if not token:
        raise ValueError("SCOPE_SERVICENOW_TOKEN not configured")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_ticket(queue_summary: dict[str, Any]) -> dict[str, Any]:
    """Create ServiceNow incident from queue state."""
    table = os.environ.get("SCOPE_SERVICENOW_TABLE", "incident")
    payload = {
        "short_description": f"SCOPE review {queue_summary.get('queue_id')}",
        "description": json.dumps(queue_summary, indent=2),
        "urgency": "2",
    }
    req = urllib.request.Request(
        f"{_snow_base()}/api/now/table/{table}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_auth_header(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return cast(dict[str, Any], data.get("result", data))


def update_ticket(ticket_id: str, queue_summary: dict[str, Any]) -> dict[str, Any]:
    """Update ServiceNow record with queue state."""
    table = os.environ.get("SCOPE_SERVICENOW_TABLE", "incident")
    payload = {"description": json.dumps(queue_summary, indent=2)}
    req = urllib.request.Request(
        f"{_snow_base()}/api/now/table/{table}/{ticket_id}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_auth_header(),
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return cast(dict[str, Any], data.get("result", data))
