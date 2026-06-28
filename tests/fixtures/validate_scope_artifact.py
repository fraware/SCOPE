#!/usr/bin/env python3
"""Local mock PCS manifest validator for CI live-contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_scope_artifact.py <pcs_dir>")
        return 1
    pcs_dir = Path(sys.argv[1])
    manifest_path = pcs_dir / "manifest.json"
    if not manifest_path.exists():
        print("Missing manifest.json")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("manifest_version", "")
    if not version.startswith("pcs-v0."):
        print(f"Invalid manifest_version: {version}")
        return 1
    print("PCS mock validator: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
