#!/usr/bin/env python3
"""Verify hash-chain integrity of a SCOPE ledger JSONL file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scope.errors import LedgerError
from scope.ledger import ScopeLedger


def verify_ledger_chain(path: Path) -> int:
    """Load ledger and verify event hash chain; return event count."""
    ledger = ScopeLedger(path)
    count = len(ledger.events())
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SCOPE ledger hash chain integrity.")
    parser.add_argument(
        "ledger",
        nargs="?",
        default=".scope/ledger.jsonl",
        help="Path to ledger JSONL file (default: .scope/ledger.jsonl)",
    )
    args = parser.parse_args()
    path = Path(args.ledger)
    if not path.is_file():
        print(f"FAIL: ledger file not found: {path}", file=sys.stderr)
        return 1
    try:
        count = verify_ledger_chain(path)
    except LedgerError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK  {count} event(s) verified in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
