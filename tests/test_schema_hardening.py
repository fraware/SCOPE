"""Schema validation hardening tests for AKTA and session artifacts."""

from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest

from scope import ScopeEngine, create_session_store
from scope.errors import SchemaValidationError
from scope.review_session import ReviewSession
from scope.schema_util import validate_artifact

ROOT = Path(__file__).resolve().parent.parent


def test_invalid_akta_record_rejected_on_packet_create():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    invalid_record = {"record_id": 12345}
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
    }
    with pytest.raises(SchemaValidationError):
        engine.create_packet(invalid_record, trigger)


def test_invalid_akta_trigger_rejected_on_packet_create():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    record = {"record_id": "AKTA-INVALID", "scientific_action_type": "A5_protocol_modification"}
    invalid_trigger = {"trigger_id": 999, "requested_tool": "protocol_editor.draft_change"}
    with pytest.raises(SchemaValidationError):
        engine.create_packet(record, invalid_trigger)


def test_invalid_session_artifact_rejected_on_save():
    store = create_session_store("memory")
    invalid_session = {
        "session_id": "SCOPE-SESS-BAD",
        "votes": [{"vote_id": "not-a-valid-vote"}],
    }
    with pytest.raises(jsonschema.ValidationError):
        store.save(invalid_session)


def test_valid_session_artifact_passes_schema():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
    }
    record = {"record_id": "AKTA-SESS-SCHEMA", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    session = ReviewSession(packet, engine.policy)
    artifact = session.to_artifact()
    validate_artifact(artifact, "scope_review_session.schema.json")
    assert "packet_snapshot" in artifact
    assert artifact["packet_snapshot"]["packet_id"] == packet["packet_id"]
