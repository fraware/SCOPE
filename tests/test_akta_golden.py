"""Golden fixture tests for AKTA nested record field mapping."""

from __future__ import annotations

import json
from pathlib import Path

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
NESTED = ROOT / "adapters" / "akta" / "examples" / "akta_record_nested.json"
GOLDEN = (
    Path(__file__).resolve().parent / "fixtures" / "contracts" / "akta_nested_golden.json"
)


def test_nested_akta_record_golden_mapping():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    packet = engine.create_packet(NESTED, {})

    req = packet["review_request"]
    ctx = packet["scientific_context"]
    constraints = packet["akta_constraints"]

    assert packet["source"]["akta_record_id"] == golden["record_id"]
    assert req["scientific_action_type"] == golden["scientific_action_type"]
    assert req["requested_action"] == golden["requested_action"]
    assert req["requested_tool"] == golden["requested_tool"]
    assert req["responsibility_level"] == golden["responsibility_level"]
    assert req["akta_admissibility"] == golden["akta_admissibility"]
    assert ctx["evidence_state"] == golden["evidence_state"]
    assert ctx["validation_status"] == golden["validation_status"]
    assert set(constraints["blocked_tools"]) == set(golden["blocked_tools"])
    assert constraints["allowed_next_steps"] == golden["allowed_next_steps"]
    assert req["requested_scope"] == golden["inferred_requested_scope"]
    assert req["scope_inference_source"] == golden["scope_inference_source"]
    assert packet["packet_version"] == "0.4.0"
