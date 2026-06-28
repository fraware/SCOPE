"""Tests for ledger sinks."""

from __future__ import annotations

import json
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from scope.ledger_sinks import (
    DeliveringSink,
    LedgerDeliveryError,
    LedgerDeliveryMode,
    LedgerSpool,
    LocalJsonlSink,
    MultiSink,
    RemoteHttpSink,
    is_high_risk_ledger_event,
)


def test_local_jsonl_sink_appends() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        sink = LocalJsonlSink(path)
        sink.append({"event_id": "E1", "event_type": "test"})
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event_id"] == "E1"


def test_remote_sink_raises_on_failure() -> None:
    sink = RemoteHttpSink("http://127.0.0.1:1/unreachable")
    with pytest.raises((urllib.error.URLError, OSError)):
        sink.append({"event_id": "E2"})


def test_multi_sink_fanout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        local = LocalJsonlSink(path)
        remote = RemoteHttpSink("http://127.0.0.1:1/unreachable")
        with patch.object(remote, "append", return_value=None):
            MultiSink([local, remote]).append({"event_id": "E3"})
        assert "E3" in path.read_text(encoding="utf-8")


def test_at_least_once_spools_failed_remote() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        spool_dir = Path(tmp) / "spool"
        remote = RemoteHttpSink("http://127.0.0.1:1/unreachable")
        with patch.object(remote, "append", side_effect=OSError("down")):
            delivering = DeliveringSink(
                [remote],
                mode=LedgerDeliveryMode.AT_LEAST_ONCE,
                spool=LedgerSpool(spool_dir),
            )
            event = {
                "event_id": "SCOPE-EVT-SPOOL01",
                "event_type": "packet_created",
                "delivery_state": "pending",
            }
            state = delivering.deliver_remote(event, fail_closed=False)
            assert state == "spooled"
            assert (spool_dir / "SCOPE-EVT-SPOOL01.json").is_file()


def test_fail_closed_raises_for_high_risk() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        local = LocalJsonlSink(path)
        remote = RemoteHttpSink("http://127.0.0.1:1/unreachable")
        with patch.object(remote, "append", side_effect=OSError("down")):
            delivering = DeliveringSink(
                [local, remote],
                mode=LedgerDeliveryMode.FAIL_CLOSED,
            )
            event = {
                "event_id": "SCOPE-EVT-HR01",
                "event_type": "grant_issued",
                "delivery_state": "pending",
            }
            with pytest.raises(LedgerDeliveryError):
                delivering.deliver_remote(event, fail_closed=True)


def test_high_risk_event_detection() -> None:
    assert is_high_risk_ledger_event("grant_issued")
    assert is_high_risk_ledger_event(
        "decision_submitted",
        {"decision_type": "approve", "approved_scope": "protocol_draft"},
    )
    assert not is_high_risk_ledger_event(
        "decision_submitted",
        {"decision_type": "approve", "approved_scope": "clarification_only"},
    )


def test_fail_closed_blocks_grant_issue(tmp_path: Path, monkeypatch) -> None:
    """High-risk grant_issued must fail when remote ledger is unavailable."""
    from scope import ScopeEngine
    from scope.errors import LedgerError
    from scope.ledger import ScopeLedger

    monkeypatch.delenv("SCOPE_LEDGER_REMOTE_URL", raising=False)
    monkeypatch.delenv("SCOPE_LEDGER_DELIVERY_MODE", raising=False)

    root = Path(__file__).resolve().parent.parent
    ex = root / "examples" / "protocol_change_review"
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(root / "policy", ledger_path=ledger)
    packet = engine.create_packet(ex / "akta_record.json", ex / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "fail_closed integration test",
        },
    )

    monkeypatch.setenv("SCOPE_LEDGER_DELIVERY_MODE", "fail_closed")
    monkeypatch.setenv("SCOPE_LEDGER_REMOTE_URL", "http://127.0.0.1:1/unreachable")
    engine.ledger = ScopeLedger(ledger)

    with pytest.raises(LedgerError, match="fail_closed"):
        engine.issue_grant(packet, decision)
