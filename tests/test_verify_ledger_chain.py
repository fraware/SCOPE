"""Tests for scripts/verify_ledger_chain.py."""

from __future__ import annotations

import json
from pathlib import Path

from scope import ScopeEngine
from scope.errors import LedgerError
from scripts.verify_ledger_chain import verify_ledger_chain


def test_verify_ledger_chain_valid(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    ledger_path = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(root / "policy", ledger_path=ledger_path)
    ex = root / "examples" / "protocol_change_review"
    packet = engine.create_packet(ex / "akta_record.json", ex / "review_trigger.json")
    engine.open_review(packet["packet_id"], actor_id="r1")
    count = verify_ledger_chain(ledger_path)
    assert count >= 2


def test_verify_ledger_chain_detects_tamper(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parent.parent
    ledger_path = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(root / "policy", ledger_path=ledger_path)
    ex = root / "examples" / "protocol_change_review"
    engine.create_packet(ex / "akta_record.json", ex / "review_trigger.json")
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[0])
    event["event_type"] = "tampered"
    lines[0] = json.dumps(event, sort_keys=True)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        verify_ledger_chain(ledger_path)
        raise AssertionError("expected LedgerError")
    except LedgerError:
        pass
