#!/usr/bin/env python3
"""Thin AKTA-side wrapper: POST review trigger/record to SCOPE REST."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def post_akta_review(
    *,
    base_url: str,
    akta_record: dict[str, Any],
    akta_trigger: dict[str, Any],
    reviewer: dict[str, Any],
    grant_scope: str,
    decision_rationale: str,
    out_dir: str | None = None,
    queue_dir: str | None = None,
    session_mode: bool = False,
    session_complete: bool = False,
    votes: list[dict[str, Any]] | None = None,
    api_key: str | None = None,
    signing_key_path: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "akta_record": akta_record,
        "akta_trigger": akta_trigger,
        "reviewer": reviewer,
        "grant_scope": grant_scope,
        "decision_rationale": decision_rationale,
    }
    if out_dir:
        payload["out_dir"] = out_dir
    if queue_dir:
        payload["queue_dir"] = queue_dir
    if session_mode:
        payload["session_mode"] = True
    if session_complete:
        payload["session_complete"] = True
    if votes:
        payload["votes"] = votes
    if signing_key_path:
        payload["signing_key_path"] = signing_key_path

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v0/akta/review",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger SCOPE AKTA review via REST.")
    parser.add_argument("--akta-record", required=True, type=Path)
    parser.add_argument("--akta-trigger", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, type=Path)
    parser.add_argument("--grant-scope", required=True)
    parser.add_argument("--decision-rationale", required=True)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--queue-dir", default=None)
    parser.add_argument("--session-mode", action="store_true")
    parser.add_argument("--session-complete", action="store_true")
    parser.add_argument("--votes", type=Path, default=None, help="Votes JSON manifest.")
    parser.add_argument(
        "--rest-url",
        default=os.environ.get("SCOPE_REST_URL", "http://127.0.0.1:8765"),
    )
    parser.add_argument("--api-key", default=os.environ.get("SCOPE_API_KEY"))
    parser.add_argument("--signing-key", default=None)
    args = parser.parse_args()

    votes = _load_json(args.votes) if args.votes else None
    if votes is not None and not isinstance(votes, list):
        votes_list = votes.get("votes") if isinstance(votes, dict) else None
        votes = votes_list if isinstance(votes_list, list) else [votes]

    try:
        summary = post_akta_review(
            base_url=args.rest_url,
            akta_record=_load_json(args.akta_record),
            akta_trigger=_load_json(args.akta_trigger),
            reviewer=_load_json(args.reviewer),
            grant_scope=args.grant_scope,
            decision_rationale=args.decision_rationale,
            out_dir=args.out_dir,
            queue_dir=args.queue_dir,
            session_mode=args.session_mode,
            session_complete=args.session_complete,
            votes=votes,
            api_key=args.api_key,
            signing_key_path=args.signing_key,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"SCOPE REST error {exc.code}: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"SCOPE REST unreachable: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
