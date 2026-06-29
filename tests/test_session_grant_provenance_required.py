"""Tests for conditional session grant provenance (SCOPE-2)."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest

from scope import ScopeEngine
from scope.errors import GrantValidationError
from scope.grants import GrantEngine
from scope.schema_util import validate_artifact
from scope.session_provenance import (
    SESSION_PROVENANCE_FIELDS,
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
    record = {"record_id": "AKTA-A6-PROV-REQ", "scientific_action_type": "A6_experimental_planning"}
    return engine.create_packet(record, trigger)


def test_single_reviewer_grant_without_session_fields_validates() -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(
        {"record_id": "AKTA-SINGLE", "scientific_action_type": "A5_protocol_modification"},
        {
            "akta_admissibility": "review_required",
            "scientific_action_type": "A5_protocol_modification",
            "requested_action": "draft_change",
            "requested_tool": "protocol_editor.draft_change",
            "requested_scope": "protocol_draft",
        },
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    grant = engine.issue_grant(packet, decision)
    validate_artifact(grant, "scope_grant.schema.json")
    validate_session_grant_provenance(grant["provenance"])


def test_session_grant_missing_provenance_fields_fails_runtime() -> None:
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
    prov = dict(grant["provenance"])
    del prov["quorum_policy_hash"]
    grant["provenance"] = prov

    grant_engine = GrantEngine(engine.policy, schema=engine._grant_engine.schema)
    with pytest.raises(GrantValidationError, match="quorum_policy_hash"):
        grant_engine.validate(grant)


def test_session_grant_partial_marker_fails_schema() -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(
        {"record_id": "AKTA-PARTIAL", "scientific_action_type": "A5_protocol_modification"},
        {
            "akta_admissibility": "review_required",
            "scientific_action_type": "A5_protocol_modification",
            "requested_action": "draft_change",
            "requested_tool": "protocol_editor.draft_change",
            "requested_scope": "protocol_draft",
        },
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    grant = engine.issue_grant(packet, decision)
    grant["provenance"]["contributing_identity_assurance_levels"] = [
        {
            "decision_id": decision["decision_id"],
            "reviewer_id": "po1",
            "identity_assurance_level": "IAL0",
        }
    ]

    grant_engine = GrantEngine(engine.policy, schema=engine._grant_engine.schema)
    with pytest.raises((GrantValidationError, jsonschema.ValidationError)):
        grant_engine.validate(grant)


def test_session_grant_includes_all_required_provenance_fields() -> None:
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
    prov = grant["provenance"]
    for field in SESSION_PROVENANCE_FIELDS:
        assert field in prov, f"missing {field}"
    validate_artifact(grant, "scope_grant.schema.json")
