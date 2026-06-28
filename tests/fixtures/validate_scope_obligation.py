#!/usr/bin/env python3
"""Local mock PF-Core obligation validator for CI live-contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_scope_obligation.py <pf_obligation.json> [grant.json]")
        return 1
    pf_path = Path(sys.argv[1])
    data = json.loads(pf_path.read_text(encoding="utf-8"))
    version = data.get("obligation_version", "")
    if not version.startswith("pf-core-v0."):
        print(f"Invalid obligation_version: {version}")
        return 1
    if not data.get("grant_id"):
        print("Missing grant_id")
        return 1
    print("PF mock validator: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
