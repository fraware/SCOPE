"""Tests for SCOPE ledger."""

from scope.hash import verify_hash
from scope.ledger import ScopeLedger


def test_hash_chain():
    ledger = ScopeLedger()
    e1 = ledger.append("packet_created", packet_id="PKT-1")
    e2 = ledger.append("decision_submitted", packet_id="PKT-1")
    assert verify_hash(e1, "event_hash")
    assert verify_hash(e2, "event_hash")
    assert e2["previous_event_hash"] == e1["event_hash"]


def test_genesis_hash():
    ledger = ScopeLedger()
    assert ledger.last_hash == ScopeLedger.GENESIS_HASH
