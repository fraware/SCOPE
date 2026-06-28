"""Tests for authority_checks provenance on decisions and grants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.authority import run_authority_checks
from scope.errors import ScopeValidationError
from scope.identity_assurance import IAL3, IdentityAssuranceContext

ROOT = Path(__file__).resolve().parent.parent


def _packet(
    action: str = "A5_protocol_modification",
    scope: str = "protocol_draft",
) -> dict:
    return {
        "packet_id": "SCOPE-PKT-AUTH",
        "review_request": {
            "scientific_action_type": action,
            "requested_scope": scope,
            "required_review_roles": ["protocol_owner"],
        },
        "scientific_context": {},
    }


def test_authority_checks_rbac_disabled_visible_in_provenance(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=tmp_path / "events.jsonl")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    packet = engine.create_packet(
        {"record_id": "AUTH-PROV", "scientific_action_type": "A5_protocol_modification"},
        trigger,
    )
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "authority provenance test",
        },
        enforce_rbac=False,
    )
    checks = decision["provenance"]["authority_checks"]
    assert checks["rbac_enforced"] is False
    assert checks["rbac_role_valid"] is False
    assert checks["scope_role_valid"] is True
    assert checks["scope_approval_valid"] is True
    assert checks["delegation_id"] is None

    grant = engine.issue_grant(packet, decision)
    grant_checks = grant["provenance"]["authority_checks"]
    assert grant_checks == checks


def test_authority_checks_rbac_vs_scope_separation_in_artifact_json() -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _packet(action="A7_queue_or_execution_change", scope="robot_queue_submission")
    decision_input = {
        "type": "approve",
        "approved_scope": "robot_queue_submission",
        "rationale": "test",
    }
    reviewer = {"reviewer_id": "ds1", "role": "domain_scientist"}
    ctx = IdentityAssuranceContext(
        identity_assurance_level=IAL3,
        role_resolution_source="org_rbac",
        identity_source="oidc_jwt",
        institutional_authority=True,
    )
    with pytest.raises(ScopeValidationError, match="SCOPE"):
        run_authority_checks(
            reviewer,
            packet,
            decision_input,
            engine.policy,
            identity_context=ctx,
            enforce_rbac=True,
        )

    block = {
        "authority_checks": {
            "rbac_enforced": True,
            "rbac_role_valid": True,
            "scope_role_valid": False,
            "scope_approval_valid": False,
            "delegation_id": None,
        }
    }
    serialized = json.dumps(block, sort_keys=True)
    assert "rbac_enforced" in serialized
    assert "scope_role_valid" in serialized
    assert "scope_approval_valid" in serialized
