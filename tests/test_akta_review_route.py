"""Tests for AKTA review_route defensive bridge (SCOPE-2)."""

from pathlib import Path

from scope import ScopeEngine
from scope.render import render_markdown

ROOT = Path(__file__).resolve().parent.parent


def test_review_scope_stored_as_review_route_not_requested_scope():
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
    assert req["requested_scope"] in ("single_validation_plan", "single_validation_run_draft")


def test_explicit_requested_scope_used():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "review_scope": "protocol_draft_to_validation_run",
    }
    record = {"record_id": "AKTA-EXPLICIT", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    req = packet["review_request"]
    assert req["requested_scope"] == "single_validation_plan"
    assert req["review_route"] == "protocol_draft_to_validation_run"
    assert req["scope_inference_source"] == "akta_trigger"


def test_render_shows_requested_scope_and_review_route():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "review_scope": "protocol_draft_to_validation_run",
    }
    record = {"record_id": "AKTA-RENDER", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    md = render_markdown(packet, engine.policy)
    assert "single_validation_plan" in md
    assert "protocol_draft_to_validation_run" in md
    assert "Review route:" in md
