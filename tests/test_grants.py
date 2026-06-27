"""Tests for SCOPE grants."""

from pathlib import Path

import pytest

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


@pytest.fixture
def grant():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "ok",
        },
    )
    return engine, engine.issue_grant(packet, decision)


def test_grant_allowed_tool(grant):
    engine, g = grant
    ctx = {"protocol_version": "protocol_v3", "evidence_state": "E2_preliminary_signal"}
    assert engine.check_grant(g, "protocol_editor.draft_change", ctx)


def test_grant_blocks_robot(grant):
    engine, g = grant
    ctx = {"protocol_version": "protocol_v3"}
    assert not engine.check_grant(g, "robot_queue.submit", ctx)


def test_grant_blocks_active_update(grant):
    engine, g = grant
    ctx = {"protocol_version": "protocol_v3"}
    assert not engine.check_grant(g, "protocol_editor.update_active_protocol", ctx)
