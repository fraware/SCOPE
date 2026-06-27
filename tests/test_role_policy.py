"""Tests for reviewer role policy."""

from pathlib import Path

import pytest

from scope.errors import RoleValidationError
from scope.policy import PolicyStore
from scope.roles import validate_reviewer_for_scope

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def policy():
    return PolicyStore.from_dir(ROOT / "policy")


def test_required_roles_for_protocol_modification(policy):
    roles = policy.get_required_roles("A5_protocol_modification")
    assert roles == ["protocol_owner"]


def test_protocol_owner_can_approve_draft(policy):
    validate_reviewer_for_scope("protocol_owner", "protocol_draft", policy)


def test_protocol_owner_cannot_approve_robot(policy):
    with pytest.raises(RoleValidationError):
        validate_reviewer_for_scope("protocol_owner", "robot_queue_submission", policy)
