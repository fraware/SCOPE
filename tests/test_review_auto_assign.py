"""Tests for review queue auto-assignment."""

from __future__ import annotations

from scope import ScopeEngine
from scope.review_auto_assign import auto_assign


def test_auto_assign_picks_domain_scientist() -> None:
    engine = ScopeEngine.from_policy_dir("policy/")
    packet = engine.create_packet(
        {"record_id": "R1", "scientific_action_type": "A6_experimental_planning"},
        {
            "akta_admissibility": "review_required",
            "scientific_action_type": "A6_experimental_planning",
            "requested_action": "plan_validation",
            "requested_tool": "experiment_planner.create_validation_plan",
            "requested_scope": "single_validation_plan",
        },
    )
    reviewer = auto_assign(packet, engine.policy)
    assert reviewer["role"] == "domain_scientist"
    assert reviewer["reviewer_id"] == "ds1"
