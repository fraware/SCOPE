"""Tests for AKTA v0.4 trigger field extraction (SCOPE-1)."""

from __future__ import annotations

import json
from pathlib import Path

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
V04_TRIGGER = ROOT / "adapters" / "akta" / "examples" / "akta_review_trigger_v04.json"
NESTED = ROOT / "adapters" / "akta" / "examples" / "akta_record_nested.json"


def test_v04_trigger_fixture_loads():
    trigger = json.loads(V04_TRIGGER.read_text(encoding="utf-8"))
    assert trigger["admissibility"] == "authorization_required"
    assert trigger["review_route"] == "protocol_draft"


def test_trigger_only_preserves_v04_fields(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = json.loads(V04_TRIGGER.read_text(encoding="utf-8"))
    packet = engine.create_packet({}, trigger)

    req = packet["review_request"]
    assert req["akta_admissibility"] == "authorization_required"
    assert req["review_route"] == "protocol_draft"
    assert req["requested_scope"] == "protocol_draft"
    assert "robot_queue.submit" in packet["akta_constraints"]["blocked_tools"]
    assert packet["akta_constraints"]["allowed_next_steps"] == ["submit_for_peer_review"]


def test_record_plus_trigger_regression():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = json.loads(V04_TRIGGER.read_text(encoding="utf-8"))
    packet = engine.create_packet(NESTED, trigger)

    assert packet["source"]["akta_record_id"] == "AKTA-SAR-V04-001"
    assert packet["review_request"]["akta_admissibility"] == "authorization_required"
    assert packet["review_request"]["review_route"] == "protocol_draft"
    assert "robot_queue.submit" in packet["akta_constraints"]["blocked_tools"]


def test_trigger_top_level_constraint_fallback():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "blocked_tools": ["instrument_control.move_stage"],
        "allowed_next_steps": ["peer_review"],
    }
    packet = engine.create_packet({}, trigger)
    assert packet["akta_constraints"]["blocked_tools"] == ["instrument_control.move_stage"]
    assert packet["akta_constraints"]["allowed_next_steps"] == ["peer_review"]
