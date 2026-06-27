"""Tests for first-class requested_scope (Priority 2)."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import ScopeValidationError

ROOT = Path(__file__).resolve().parent.parent
DRIFT = ROOT / "examples" / "protocol_drift"


def test_explicit_requested_scope_from_trigger():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(DRIFT / "akta_record.json", DRIFT / "review_trigger.json")
    assert packet["review_request"]["requested_scope"] == "protocol_draft"
    assert packet["review_request"]["scope_inference_source"] == "akta_trigger"


def test_protocol_draft_scoped_approval():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(DRIFT / "akta_record.json", DRIFT / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    assert decision["decision"]["approved_scope"] == "protocol_draft"


def test_overbroad_rejection_against_requested_scope():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(DRIFT / "akta_record.json", DRIFT / "review_trigger.json")
    with pytest.raises(ScopeValidationError, match="stronger than requested"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "r1", "role": "protocol_owner"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "active_protocol_update",
                "rationale": "too broad",
            },
        )


def test_queue_prioritization_requested_scope():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A7_resource_or_queue_prioritization",
        "requested_action": "prioritize_queue",
        "requested_tool": "lab_scheduler.prioritize",
        "requested_scope": "single_run_queue_priority",
    }
    record = {
        "record_id": "AKTA-Q",
        "scientific_action_type": "A7_resource_or_queue_prioritization",
    }
    packet = engine.create_packet(record, trigger)
    assert packet["review_request"]["requested_scope"] == "single_run_queue_priority"


def test_robot_submission_unknown_scope_rejected():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A4_recommendation",
        "requested_action": "recommend",
        "requested_tool": "unknown.custom_tool",
    }
    record = {"record_id": "AKTA-R", **trigger}
    packet = engine.create_packet(record, {})
    assert packet["review_request"]["scope_inference_source"] == "unknown"
    with pytest.raises(ScopeValidationError, match="unknown"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "r1", "role": "domain_scientist"},
            {
                "type": "approve",
                "approved_scope": "draft_recommendation",
                "rationale": "no explicit scope",
            },
        )


def test_system_owner_override_unknown_scope():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "authorization_required",
        "scientific_action_type": "A8_tool_or_workflow_mutation",
        "requested_action": "mutate",
        "requested_tool": "unknown.custom_tool",
    }
    packet = engine.create_packet({"record_id": "X", **trigger}, {})
    assert packet["review_request"]["scope_inference_source"] == "unknown"
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "so", "role": "system_owner"},
        {
            "type": "approve",
            "approved_scope": "tool_permission_escalation",
            "rationale": "system owner override",
        },
    )
    assert decision["decision"]["approved_scope"] == "tool_permission_escalation"
