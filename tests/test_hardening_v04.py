"""Tests for scope inference and domain overlays."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import DecisionValidationError
from scope.policy import PolicyStore

ROOT = Path(__file__).resolve().parent.parent


def test_review_route_promoted_to_requested_scope():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "review_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-PROMO", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    req = packet["review_request"]
    assert req["requested_scope"] == "protocol_draft"
    assert req["scope_inference_source"] == "review_route_promoted"


def test_invalid_review_route_not_promoted():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "review_scope": "experimental_plan_review",
    }
    record = {"record_id": "AKTA-ROUTE", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    req = packet["review_request"]
    assert req.get("review_route") == "experimental_plan_review"
    assert req.get("requested_scope") != "experimental_plan_review"
    assert req["scope_inference_source"] == "tool_registry"


def test_domain_overlay_modifies_required_roles():
    policy = PolicyStore.from_dir(ROOT / "policy")
    base = policy.get_required_roles("A8_tool_or_workflow_mutation")
    overlay = policy.get_required_roles(
        "A8_tool_or_workflow_mutation", domain_overlay="genomics_research"
    )
    assert "biosecurity_reviewer" in overlay
    assert len(overlay) > len(base)


def test_robot_queue_requires_session():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A9_execution_adjacent_or_external_action",
        "requested_action": "submit_robot_queue",
        "requested_tool": "robot_queue.submit",
        "requested_scope": "robot_queue_submission",
    }
    record = {
        "record_id": "AKTA-ROBOT",
        "scientific_action_type": "A9_execution_adjacent_or_external_action",
    }
    packet = engine.create_packet(record, trigger)
    with pytest.raises(DecisionValidationError, match="review session"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "so1", "role": "system_owner"},
            {
                "type": "approve",
                "approved_scope": "robot_queue_submission",
                "rationale": "solo approval",
            },
        )


def test_a8_requires_session():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A8_tool_or_workflow_mutation",
        "requested_action": "mutate_permissions",
        "requested_tool": "workflow.mutate_permissions",
        "requested_scope": "tool_permission_escalation",
    }
    record = {"record_id": "AKTA-A8", "scientific_action_type": "A8_tool_or_workflow_mutation"}
    packet = engine.create_packet(record, trigger)
    with pytest.raises(DecisionValidationError, match="review session"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "so1", "role": "system_owner"},
            {
                "type": "approve",
                "approved_scope": "tool_permission_escalation",
                "rationale": "solo",
            },
        )


def test_co_reviewers_rejected_for_require_all():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
    }
    record = {"record_id": "AKTA-CO", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    with pytest.raises(DecisionValidationError, match="co_reviewers"):
        engine.submit_decision(
            packet,
            {"reviewer_id": "ds1", "role": "domain_scientist"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "single_validation_plan",
                "rationale": "solo with co_reviewers",
                "co_reviewers": ["protocol_owner"],
            },
        )


def test_domain_overlay_changes_packet_required_roles():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    base_trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A8_tool_or_workflow_mutation",
        "requested_action": "mutate_permissions",
        "requested_tool": "workflow.mutate_permissions",
        "requested_scope": "tool_permission_escalation",
    }
    record = {
        "record_id": "AKTA-OVERLAY-E2E",
        "scientific_action_type": "A8_tool_or_workflow_mutation",
    }
    base_packet = engine.create_packet(record, base_trigger)
    overlay_trigger = {
        **base_trigger,
        "scientific_context": {"domain_overlay": "genomics_research"},
    }
    overlay_packet = engine.create_packet(record, overlay_trigger)
    base_roles = set(base_packet["review_request"]["required_review_roles"])
    overlay_roles = set(overlay_packet["review_request"]["required_review_roles"])
    assert "biosecurity_reviewer" in overlay_roles
    assert overlay_roles != base_roles
