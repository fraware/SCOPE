"""Tests for SCOPE decisions."""

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.errors import RoleValidationError, ScopeValidationError

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


@pytest.fixture
def engine():
    return ScopeEngine.from_policy_dir(ROOT / "policy")


@pytest.fixture
def packet(engine):
    return engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")


def test_submit_narrower_decision(engine, packet):
    reviewer = {
        "reviewer_id": "reviewer_001",
        "role": "protocol_owner",
    }
    decision = engine.submit_decision(
        packet,
        reviewer,
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "Draft only.",
        },
    )
    assert decision["decision"]["approved_scope"] == "protocol_draft"
    assert decision["decision_hash"].startswith("sha256:")


def test_reject_wrong_reviewer(engine, packet):
    with pytest.raises(RoleValidationError):
        engine.submit_decision(
            packet,
            {"reviewer_id": "x", "role": "domain_scientist"},
            {"type": "reject", "rationale": "no"},
        )


def test_reject_overbroad_scope(engine, packet):
    with pytest.raises((ScopeValidationError, RoleValidationError)):
        engine.submit_decision(
            packet,
            {"reviewer_id": "x", "role": "protocol_owner"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "robot_queue_submission",
                "rationale": "too broad",
            },
        )
