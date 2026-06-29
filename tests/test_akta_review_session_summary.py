"""Tests for split AKTA review summary schemas (SCOPE-1)."""

from __future__ import annotations

import jsonschema
import pytest

from scope.akta_review import validate_summary_artifact
from scope.errors import ScopeValidationError
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION
from scope.schema_util import validate_artifact


def _completed_summary(**overrides: object) -> dict:
    base: dict = {
        "status": "completed",
        "packet_path": "/out/scope_review_packet.json",
        "decision_path": "/out/scope_decision.json",
        "grant_path": "/out/scope_grant.json",
        "approved_scope": "protocol_draft",
        "requested_scope": "protocol_draft",
        "adapter_contract_version": AKTA_REVIEW_CONTRACT_VERSION,
        "identity_assurance_level": "IAL0",
        "signing_assurance_level": "SAL0",
        "production_mode": False,
    }
    base.update(overrides)
    return base


def _session_summary(**overrides: object) -> dict:
    base: dict = {
        "status": "session_required",
        "packet_id": "SCOPE-PKT-TEST01",
        "session_id": "SCOPE-SESS-TEST01",
        "required_roles": ["domain_scientist", "protocol_owner"],
        "message": "Multi-role review session created; submit votes before grant issue.",
        "adapter_contract_version": AKTA_REVIEW_CONTRACT_VERSION,
        "production_mode": False,
    }
    base.update(overrides)
    return base


def test_completed_summary_schema_accepts_valid_shape() -> None:
    validate_artifact(_completed_summary(), "scope_akta_review_summary.schema.json")
    validate_summary_artifact(_completed_summary())


def test_session_summary_schema_accepts_valid_shape() -> None:
    validate_artifact(
        _session_summary(),
        "scope_akta_review_session_summary.schema.json",
    )
    validate_summary_artifact(_session_summary())


def test_completed_schema_rejects_session_fields() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact(
            _completed_summary(session_id="SCOPE-SESS-BAD"),
            "scope_akta_review_summary.schema.json",
        )


def test_completed_schema_rejects_session_required_status() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact(
            _session_summary(),
            "scope_akta_review_summary.schema.json",
        )


def test_session_schema_rejects_completed_fields() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact(
            _session_summary(
                decision_path="/out/scope_decision.json",
                grant_path="/out/scope_grant.json",
            ),
            "scope_akta_review_session_summary.schema.json",
        )


def test_session_schema_rejects_completed_status() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact(
            _completed_summary(),
            "scope_akta_review_session_summary.schema.json",
        )


def test_validate_summary_artifact_rejects_unknown_status() -> None:
    with pytest.raises(ScopeValidationError, match="summary.status must be"):
        validate_summary_artifact({"status": "pending"})


def test_validate_summary_artifact_rejects_cross_branch_fields() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_summary_artifact(
            _session_summary(
                decision_path="/out/scope_decision.json",
                grant_path="/out/scope_grant.json",
            )
        )
    with pytest.raises(jsonschema.ValidationError):
        validate_summary_artifact(_completed_summary(session_id="SCOPE-SESS-BAD"))


def test_completed_schema_requires_status_completed() -> None:
    summary = _completed_summary()
    del summary["status"]
    with pytest.raises(jsonschema.ValidationError):
        validate_artifact(summary, "scope_akta_review_summary.schema.json")
