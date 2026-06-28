"""Fetch VSA ScientificReport from remote URL or configured API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.vsa.import_report import import_vsa_report


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_vsa_report(
    *,
    url: str | None = None,
    report_id: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Fetch VSA report JSON from URL or VSA_API_URL + report_id."""
    target = url
    if not target:
        api_base = os.environ.get("VSA_API_URL")
        if not api_base or not report_id:
            raise ValueError("Provide --vsa-url or VSA_API_URL with report_id")
        target = f"{api_base.rstrip('/')}/reports/{report_id}"

    headers = {"Accept": "application/json"}
    auth_token = token or os.environ.get("VSA_API_TOKEN")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = urllib.request.Request(target, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ValueError(f"Failed to fetch VSA report from {target}: {exc}") from exc

    enriched = import_vsa_report(raw)
    enriched["fetched_at"] = _utc_now()
    enriched["source_url"] = target
    return enriched


def fetch_vsa_report_from_file_or_url(
    source: str | Path,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    """Load from local path or HTTP(S) URL."""
    text = str(source)
    if text.startswith("http://") or text.startswith("https://"):
        return fetch_vsa_report(url=text, token=token)
    return import_vsa_report(source)
