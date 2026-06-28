"""Tests for review assignment resolution engine."""

from __future__ import annotations

from pathlib import Path

from scope import ScopeEngine
from scope.policy import PolicyStore
from scope.review_assignment import resolve_review_assignment
from scope.schema_util import validate_artifact

ROOT = Path(__file__).resolve().parent.parent


def test_resolve_review_assignment_base_action():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
    }
    record = {"record_id": "AKTA-RA", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    assignment = resolve_review_assignment(packet, engine.policy)

    assert assignment["action_type"] == "A6_experimental_planning"
    assert set(assignment["required_roles"]) == {"domain_scientist", "protocol_owner"}
    assert assignment["quorum_mode"] == "require_all"
    assert assignment["packet_id"] == packet["packet_id"]
    validate_artifact(assignment, "review_assignment.schema.json")


def test_resolve_review_assignment_with_domain_overlay():
    policy = PolicyStore.from_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A8_tool_or_workflow_mutation",
        "requested_action": "mutate_permissions",
        "requested_tool": "workflow.mutate_permissions",
        "requested_scope": "tool_permission_escalation",
        "scientific_context": {"domain_overlay": "genomics_research"},
    }
    record = {"record_id": "AKTA-OVERLAY", "scientific_action_type": "A8_tool_or_workflow_mutation"}
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(record, trigger)
    assignment = resolve_review_assignment(packet, policy)

    assert assignment["domain_overlay"] == "genomics_research"
    assert "biosecurity_reviewer" in assignment["required_roles"]
    validate_artifact(assignment, "review_assignment.schema.json")
