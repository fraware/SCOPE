#!/usr/bin/env python3
"""Simulate PF-Core runtime block and record violation in SCOPE ledger."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.pf_core.export_obligation import export_pf_obligation


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _pick_blocked_tool(obligation: dict) -> tuple[str, str]:
    blocked = obligation.get("blocked_tools") or []
    if blocked:
        tool = str(blocked[0])
        return tool, f"PF blocked disallowed tool {tool}"
    permitted = obligation.get("permitted_tools") or []
    if permitted:
        tool = str(permitted[0])
        return tool, f"PF simulated scope violation for {tool}"
    return "unknown.tool", "PF simulated runtime scope violation"


def _record_via_cli(grant_id: str, tool: str, reason: str, ledger: Path, policy: Path) -> dict:
    from scope import ScopeEngine

    engine = ScopeEngine.from_policy_dir(policy, ledger_path=ledger)
    return engine.record_runtime_violation(grant_id, tool=tool, reason=reason)


def _record_via_rest(
    grant_id: str,
    tool: str,
    reason: str,
    *,
    base_url: str,
    api_key: str | None,
) -> dict:
    payload = json.dumps({"grant_id": grant_id, "tool": tool, "reason": reason}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v0/ledger/violations",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject PF runtime violation into SCOPE ledger.")
    parser.add_argument("--grant", required=True, type=Path, help="SCOPE grant JSON path.")
    parser.add_argument("--ledger", type=Path, default=Path(".scope/ledger.jsonl"))
    parser.add_argument("--policy", type=Path, default=Path("policy"))
    parser.add_argument("--tool", default=None, help="Tool name to record (default: from obligation).")
    parser.add_argument("--reason", default=None, help="Violation reason.")
    parser.add_argument(
        "--rest-url",
        default=os.environ.get("SCOPE_REST_URL"),
        help="SCOPE REST base URL (optional; default CLI ledger append).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SCOPE_API_KEY"),
        help="REST bearer token when using --rest-url.",
    )
    args = parser.parse_args()

    grant = _load_json(args.grant)
    obligation = export_pf_obligation(grant)
    tool, default_reason = _pick_blocked_tool(obligation)
    tool = args.tool or tool
    reason = args.reason or default_reason
    grant_id = str(grant["grant_id"])

    if args.rest_url:
        try:
            event = _record_via_rest(
                grant_id, tool, reason, base_url=args.rest_url, api_key=args.api_key
            )
        except urllib.error.URLError as exc:
            print(f"REST violation record failed: {exc}", file=sys.stderr)
            return 1
    else:
        event = _record_via_cli(grant_id, tool, reason, args.ledger, args.policy)

    print(json.dumps({"simulated_pf_block": True, "tool": tool, "event": event}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
