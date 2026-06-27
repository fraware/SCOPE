"""Tests for reviewer and role quality analytics (Priority 6)."""

from scope.ledger import ScopeLedger
from scope.policy import PolicyStore
from scope.quality import analyze_ledger

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_fast_approval_reviewer_metrics():
    policy = PolicyStore.from_dir(ROOT / "policy")
    ledger = ScopeLedger()
    ledger.append(
        "decision_submitted",
        actor_id="reviewer_fast",
        reviewer_role="protocol_owner",
        metadata={
            "decision_type": "approve_narrower_scope",
            "review_duration_seconds": 5,
            "scientific_action_type": "A5_protocol_modification",
        },
    )
    report = analyze_ledger(ledger.events(), policy)
    assert report["by_reviewer"]["reviewer_fast"]["fast_approvals"] == 1
    assert report["by_role"]["protocol_owner"]["decisions"] == 1


def test_stale_grant_by_action_type():
    policy = PolicyStore.from_dir(ROOT / "policy")
    ledger = ScopeLedger()
    ledger.append(
        "grant_expired",
        grant_id="G1",
        metadata={
            "reason": "Protocol version changed",
            "scientific_action_type": "A5_protocol_modification",
        },
    )
    report = analyze_ledger(ledger.events(), policy)
    assert any(w["warning_type"] == "stale_grant_attempt" for w in report["warnings"])


def test_role_distinction():
    policy = PolicyStore.from_dir(ROOT / "policy")
    ledger = ScopeLedger()
    ledger.append(
        "decision_submitted",
        actor_id="ds1",
        reviewer_role="domain_scientist",
        metadata={"decision_type": "approve", "scientific_action_type": "A4_recommendation"},
    )
    ledger.append(
        "decision_submitted",
        actor_id="po1",
        reviewer_role="protocol_owner",
        metadata={
            "decision_type": "approve_narrower_scope",
            "scientific_action_type": "A5_protocol_modification",
        },
    )
    report = analyze_ledger(ledger.events(), policy)
    assert report["by_role"]["domain_scientist"]["decisions"] == 1
    assert report["by_role"]["protocol_owner"]["decisions"] == 1
    assert "summary" in report
