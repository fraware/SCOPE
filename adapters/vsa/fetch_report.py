"""Fetch VSA ScientificReport from remote URL or configured API."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
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


def schedule_vsa_refetch(
    *,
    report_id: str | None = None,
    url: str | None = None,
    interval_seconds: int = 3600,
    on_refresh: Callable[[dict[str, Any]], None] | None = None,
    max_iterations: int | None = None,
    token: str | None = None,
) -> None:
    """
    Scheduled re-fetch hook for evidence refresh pipelines.

    Downstream systems should compare ``evidence_summary.overall_state`` across
    fetches and invoke grant expiration rules when evidence downgrades.
    """
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        report = fetch_vsa_report(url=url, report_id=report_id, token=token)
        if on_refresh is not None:
            on_refresh(report)
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            break
        time.sleep(max(interval_seconds, 1))


def _cli_main() -> int:
    parser = argparse.ArgumentParser(description="Fetch or schedule VSA report re-fetch.")
    parser.add_argument("--url", default=None)
    parser.add_argument("--report-id", default=None)
    parser.add_argument(
        "--interval", type=int, default=0, help="Seconds between fetches (0 = once)."
    )
    parser.add_argument("--once", action="store_true", help="Fetch once and exit.")
    parser.add_argument("--out", type=Path, default=None, help="Write fetched report JSON.")
    args = parser.parse_args()

    def _emit(report: dict[str, Any]) -> None:
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            print(json.dumps(report, indent=2))

    if args.once or args.interval <= 0:
        _emit(fetch_vsa_report(url=args.url, report_id=args.report_id))
        return 0

    schedule_vsa_refetch(
        report_id=args.report_id,
        url=args.url,
        interval_seconds=args.interval,
        on_refresh=_emit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
