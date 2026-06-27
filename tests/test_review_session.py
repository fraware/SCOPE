"""Tests for multi-review workflow (Priority 5)."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import GrantValidationError

ROOT = Path(__file__).resolve().parent.parent


def _a6_packet(engine):
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "scientific_context": {
            "protocol_version": "protocol_v1",
            "evidence_state": "E1_hypothesis",
        },
    }
    record = {"record_id": "AKTA-A6", "scientific_action_type": "A6_experimental_planning"}
    return engine.create_packet(record, trigger)


def test_a6_requires_both_roles():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    assert set(packet["review_request"]["required_review_roles"]) == {
        "domain_scientist",
        "protocol_owner",
    }


def test_one_decision_alone_no_grant():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    d1 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    assert d1["decision_id"]
    with pytest.raises(GrantValidationError, match="missing roles"):
        engine.issue_grant_from_session(session, packet, [d1])


def test_two_valid_reviews_grant():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    d1 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    d2 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    grant = engine.issue_grant_from_session(session, packet, [d1, d2])
    assert grant["authorization"]["approved_scope"] == "single_validation_plan"


def test_conflict_blocks_grant():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    d1 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    d2 = engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "narrower",
        },
    )
    with pytest.raises(GrantValidationError, match="Conflicting"):
        engine.issue_grant_from_session(session, packet, [d1, d2])


def test_safety_veto_blocks():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    session = engine.create_review_session(
        packet,
        quorum_policy={
            "mode": "require_all",
            "required_roles": packet["review_request"]["required_review_roles"],
            "safety_veto_roles": ["safety_officer"],
        },
    )
    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "so1", "role": "safety_officer"},
        {"type": "reject", "rationale": "unsafe conditions"},
    )
    assert session.status() == "safety_veto"
    with pytest.raises(GrantValidationError, match="Safety veto"):
        session.resolve()
