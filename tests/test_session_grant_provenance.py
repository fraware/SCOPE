"""Tests for session grant provenance aggregation (SCOPE-2)."""

from __future__ import annotations

from pathlib import Path

from scope import ScopeEngine
from scope.hash import compute_hash
from scope.schema_util import validate_artifact
from scope.session_provenance import (
    SESSION_PROVENANCE_FIELDS,
    aggregate_session_grant_provenance,
    is_session_grant_provenance,
    validate_session_grant_provenance,
)

ROOT = Path(__file__).resolve().parent.parent


def _a6_packet(engine: ScopeEngine) -> dict:
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "scientific_context": {"protocol_version": "protocol_v1"},
    }
    record = {"record_id": "AKTA-A6-PROV", "scientific_action_type": "A6_experimental_planning"}
    return engine.create_packet(record, trigger)


def test_session_grant_includes_aggregated_provenance() -> None:
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
    prov = grant["provenance"]

    assert len(prov["contributing_identity_assurance_levels"]) == 2
    reviewer_ids = {
        entry["reviewer_id"] for entry in prov["contributing_identity_assurance_levels"]
    }
    assert reviewer_ids == {"ds1", "po1"}

    assert len(prov["contributing_authority_checks"]) == 2
    assert prov["minimum_identity_assurance_level"] == "IAL0"
    assert prov["minimum_signing_assurance_level"] == "SAL0"
    assert prov["veto_roles_applied"] == ["safety_officer"]
    assert prov["quorum_policy_hash"] == compute_hash(session.quorum_policy)
    assert prov["quorum_policy_hash"].startswith("sha256:")

    session_fields = SESSION_PROVENANCE_FIELDS
    for field in session_fields:
        assert field in prov, f"missing session provenance field: {field}"
    assert is_session_grant_provenance(prov)
    validate_session_grant_provenance(prov)
    validate_artifact(grant, "scope_grant.schema.json")


def test_aggregate_session_grant_provenance_unit() -> None:
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
    aggregated = aggregate_session_grant_provenance(session, [d1])
    assert aggregated["minimum_identity_assurance_level"] == "IAL0"
    assert aggregated["contributing_identity_assurance_levels"][0]["reviewer_id"] == "ds1"
    assert aggregated["veto_roles_applied"] == []
