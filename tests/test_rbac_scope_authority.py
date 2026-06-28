"""Tests for two-stage RBAC vs SCOPE authority separation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.authority import enforce_decision_authority
from scope.errors import ScopeValidationError
from scope.identity_assurance import IAL3, IdentityAssuranceContext

ROOT = Path(__file__).resolve().parent.parent


def _packet(action: str = "A7_queue_or_execution_change", scope: str = "robot_queue_submission"):
    return {
        "packet_id": "SCOPE-PKT-TEST",
        "review_request": {
            "scientific_action_type": action,
            "requested_scope": scope,
            "required_review_roles": ["lab_operations_lead"],
        },
        "scientific_context": {},
    }


def test_domain_scientist_cannot_approve_robot_queue() -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _packet()
    decision = {
        "type": "approve",
        "approved_scope": "robot_queue_submission",
        "rationale": "test",
    }
    reviewer = {"reviewer_id": "ds1", "role": "domain_scientist"}
    ctx = IdentityAssuranceContext(
        identity_assurance_level=IAL3,
        role_resolution_source="org_rbac",
        institutional_authority=True,
    )
    with pytest.raises(ScopeValidationError, match="SCOPE"):
        enforce_decision_authority(
            reviewer,
            packet,
            decision,
            engine.policy,
            identity_context=ctx,
            enforce_rbac=True,
        )


def test_protocol_owner_cannot_approve_robot_queue() -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = {
        "packet_id": "SCOPE-PKT-PO",
        "review_request": {
            "scientific_action_type": "A5_protocol_modification",
            "requested_scope": "protocol_draft",
            "required_review_roles": ["protocol_owner"],
        },
        "scientific_context": {},
    }
    decision = {
        "type": "approve_narrower_scope",
        "approved_scope": "robot_queue_submission",
        "rationale": "too broad",
    }
    reviewer = {"reviewer_id": "po1", "role": "protocol_owner"}
    with pytest.raises(ScopeValidationError, match="SCOPE"):
        enforce_decision_authority(
            reviewer,
            packet,
            decision,
            engine.policy,
            enforce_rbac=False,
        )


def test_domain_scientist_cannot_decide_protocol_modification() -> None:
    """A5 requires protocol_owner; domain_scientist lacks action authority."""
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = {
        "packet_id": "SCOPE-PKT-DS-A5",
        "review_request": {
            "scientific_action_type": "A5_protocol_modification",
            "requested_scope": "protocol_draft",
            "required_review_roles": ["protocol_owner"],
        },
        "scientific_context": {},
    }
    decision = {
        "type": "approve_narrower_scope",
        "approved_scope": "protocol_draft",
        "rationale": "policy forbids this role for A5",
    }
    reviewer = {"reviewer_id": "ds1", "role": "domain_scientist"}
    with pytest.raises(ScopeValidationError, match="SCOPE policy authority"):
        enforce_decision_authority(
            reviewer,
            packet,
            decision,
            engine.policy,
            enforce_rbac=False,
        )


def test_expired_delegation_invalidates_authority(tmp_path: Path) -> None:
    import shutil

    policy_dir = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_dir)
    org_rbac = {
        "version": "scope-core-v0.7",
        "org_units": {},
        "delegations": [
            {
                "delegate_reviewer_id": "ds1",
                "role": "domain_scientist",
                "granted_to": "ds_expired",
                "valid_until": "2020-01-01T00:00:00Z",
                "granted_by": "principal_investigator",
            }
        ],
        "role_permissions": {
            "domain_scientist": {
                "can_submit_decisions": True,
                "can_vote_in_session": True,
            }
        },
    }
    import yaml

    with (policy_dir / "org_rbac.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(org_rbac, fh)

    engine = ScopeEngine.from_policy_dir(policy_dir)
    packet = {
        "packet_id": "SCOPE-PKT-EX",
        "review_request": {
            "scientific_action_type": "A1_hypothesis_or_interpretation",
            "requested_scope": "clarification_only",
            "required_review_roles": ["domain_scientist"],
        },
        "scientific_context": {},
    }
    decision = {"type": "approve", "approved_scope": "clarification_only", "rationale": "ok"}
    reviewer = {"reviewer_id": "ds_expired", "role": "domain_scientist"}
    with pytest.raises(ScopeValidationError, match="RBAC|delegation"):
        enforce_decision_authority(
            reviewer,
            packet,
            decision,
            engine.policy,
            enforce_rbac=True,
            at=datetime.now(timezone.utc),
        )
