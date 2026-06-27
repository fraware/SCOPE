"""Tests for AKTA-to-SCOPE bridge (Priority 1)."""

import json
from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import SchemaValidationError

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"
NESTED = ROOT / "adapters" / "akta" / "examples" / "akta_record_nested.json"


def test_flat_record_and_trigger():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    assert packet["source"]["akta_record_id"] == "AKTA-SAR-000001"
    assert packet["review_request"]["requested_tool"] == "protocol_editor.update_active_protocol"
    assert packet["review_request"]["scope_inference_source"] == "tool_registry"


def test_nested_record_with_trigger():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "trigger_id": "TRIG-NESTED",
        "akta_admissibility": "review_required",
        "scientific_context": {"protocol_version": "protocol_v3", "domain": "materials"},
    }
    packet = engine.create_packet(NESTED, trigger)
    assert packet["source"]["akta_record_id"] == "AKTA-SAR-NESTED-001"
    assert packet["review_request"]["scientific_action_type"] == "A5_protocol_modification"
    assert packet["scientific_context"]["evidence_state"] == "E2_preliminary_signal"
    assert "robot_queue.submit" in packet["akta_constraints"]["blocked_tools"]
    assert packet["akta_constraints"]["allowed_next_steps"]


def test_record_alone():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    record = json.loads(NESTED.read_text())
    record["requested_transition"]["requested_action"] = "update_active_protocol"
    record["requested_transition"]["requested_tool"] = "protocol_editor.update_active_protocol"
    packet = engine.create_packet(record, {})
    assert packet["review_request"]["requested_action"] == "update_active_protocol"


def test_trigger_alone():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = json.loads((EX / "review_trigger.json").read_text())
    packet = engine.create_packet({}, trigger)
    assert packet["review_request"]["requested_tool"] == "protocol_editor.update_active_protocol"


def test_missing_tool_raises():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    with pytest.raises(SchemaValidationError, match="requested_tool"):
        engine.create_packet({"scientific_action_type": "A5_protocol_modification"}, {})


def test_missing_action_type_raises():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    with pytest.raises(SchemaValidationError, match="scientific_action_type"):
        engine.create_packet({"requested_tool": "comment.add"}, {})


def test_nested_paths_mapped():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(NESTED, {})
    assert packet["review_request"]["responsibility_level"] == "R4_methodological_modification"
    assert packet["review_request"]["akta_admissibility"] == "review_required"
    assert packet["scientific_context"]["validation_status"] == "V1_literature_supported"
