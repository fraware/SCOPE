"""Tests for quality metrics."""

from scope.ledger import ScopeLedger
from scope.policy import PolicyStore
from scope.quality import analyze_ledger

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_quality_report_from_events():
    policy = PolicyStore.from_dir(ROOT / "policy")
    ledger = ScopeLedger()
    ledger.append(
        "decision_submitted",
        metadata={"decision_type": "approve_narrower_scope", "review_duration_seconds": 120},
    )
    report = analyze_ledger(ledger.events(), policy)
    assert "metrics" in report
    assert "warnings" in report
