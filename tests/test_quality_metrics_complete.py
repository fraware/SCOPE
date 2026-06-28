"""Comprehensive quality metrics tests (v0.4)."""

from __future__ import annotations

from scope import ScopeEngine
from scope.ledger import ScopeLedger
from scope.policy import PolicyStore
from scope.quality import analyze_ledger

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def _engine_with_ledger(tmp_path):
    ledger = tmp_path / "events.jsonl"
    return ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger), ledger


def test_all_deferred_metrics_present():
    policy = PolicyStore.from_dir(ROOT / "policy")
    report = analyze_ledger([], policy)
    metrics = report["metrics"]
    expected = [
        "reviewer_confidence_variance",
        "repeat_approval_rate",
        "high_risk_approval_rate",
        "approval_despite_low_evidence_rate",
        "approval_despite_akta_block_rate",
        "residual_block_preservation_rate",
        "review_queue_length",
        "open_queue_count",
        "overdue_queue_count",
        "median_time_to_decision",
        "reviewer_load",
        "duplicate_review_rate",
        "unnecessary_review_rate",
        "false_review_trigger_rate",
        "post_approval_failure_rate",
        "post_approval_protocol_drift_rate",
        "post_approval_evidence_downgrade_rate",
        "post_approval_runtime_violation_rate",
    ]
    for key in expected:
        assert key in metrics, f"Missing metric: {key}"
    assert report["report_version"] == "0.6"


def test_low_evidence_warning_and_rate(tmp_path):
    engine, _ = _engine_with_ledger(tmp_path)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {"evidence_state": "E0_unknown"},
    }
    record = {"record_id": "AKTA-QM", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    report = engine.quality_report()
    assert report["metrics"]["approval_despite_low_evidence_rate"] > 0
    warning_types = {w["warning_type"] for w in report["warnings"]}
    assert "approval_despite_low_evidence" in warning_types


def test_residual_block_preservation_rate(tmp_path):
    engine, _ = _engine_with_ledger(tmp_path)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "akta_constraints": {"blocked_tools": ["robot_queue.submit"]},
    }
    record = {"record_id": "AKTA-RES", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    engine.issue_grant(packet, decision)
    report = engine.quality_report()
    assert report["metrics"]["residual_block_preservation_rate"] == 1.0


def test_review_queue_and_reviewer_load(tmp_path):
    engine, _ = _engine_with_ledger(tmp_path)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-QUEUE", "scientific_action_type": "A5_protocol_modification"}
    engine.create_packet(record, trigger)
    engine.create_packet(record, trigger)
    report = engine.quality_report()
    assert report["metrics"]["review_queue_length"] == 2
    assert report["metrics"]["review_assigned_count"] == 2


def test_confidence_variance():
    policy = PolicyStore.from_dir(ROOT / "policy")
    ledger = ScopeLedger()
    for conf in (0.2, 0.8):
        ledger.append(
            "decision_submitted",
            metadata={"decision_type": "approve", "reviewer_confidence": conf},
        )
    report = analyze_ledger(ledger.events(), policy)
    assert report["metrics"]["reviewer_confidence_variance"] is not None
    assert report["metrics"]["reviewer_confidence_variance"] > 0


def test_post_approval_runtime_violation_rate(tmp_path):
    engine, _ = _engine_with_ledger(tmp_path)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-VIO", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    grant = engine.issue_grant(packet, decision)
    engine.check_grant(grant, "robot_queue.submit", {})
    report = engine.quality_report()
    assert report["metrics"]["post_approval_runtime_violation_rate"] > 0
