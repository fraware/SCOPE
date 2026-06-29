"""Tests for scope akta review --session control flow (SCOPE-1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scope import ScopeEngine
from scope.akta_review import run_akta_review
from scope.cli import main
from scope.errors import ScopeValidationError
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION
from scope.schema_util import validate_artifact

ROOT = Path(__file__).resolve().parent.parent
WEAK = ROOT / "examples" / "weak_evidence_validation_review"


def _a6_trigger() -> dict:
    return {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "scientific_context": {
            "protocol_version": "protocol_v1",
            "evidence_state": "E1_hypothesis",
        },
    }


def test_multi_role_without_session_fails_explicit_message(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    with pytest.raises(ScopeValidationError, match="multi-role review session"):
        run_akta_review(
            engine,
            akta_record={
                "record_id": "AKTA-A6",
                "scientific_action_type": "A6_experimental_planning",
            },
            akta_trigger=_a6_trigger(),
            grant_scope="single_validation_plan",
            reviewer={"reviewer_id": "ds1", "role": "domain_scientist"},
            decision_rationale="solo attempt",
            out_dir=tmp_path / "out",
        )


def test_multi_role_with_session_creates_session(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    out_dir = tmp_path / "session_out"
    summary = run_akta_review(
        engine,
        akta_record={
            "record_id": "AKTA-A6",
            "scientific_action_type": "A6_experimental_planning",
        },
        akta_trigger=_a6_trigger(),
        grant_scope="single_validation_plan",
        reviewer=WEAK / "reviewer_protocol_owner.json",
        decision_rationale="session path",
        out_dir=out_dir,
        session_mode=True,
    )
    assert summary["status"] == "session_required"
    assert summary["session_id"].startswith("SCOPE-SESS-")
    assert set(summary["required_roles"]) == {"domain_scientist", "protocol_owner"}
    assert (out_dir / "scope_review_packet.json").exists()
    assert (out_dir / "summary.json").exists()
    assert not (out_dir / "scope_grant.json").exists()

    on_disk = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    validate_artifact(on_disk, "scope_akta_review_session_summary.schema.json")
    assert on_disk["adapter_contract_version"] == AKTA_REVIEW_CONTRACT_VERSION


def test_akta_review_cli_session_flag(tmp_path: Path) -> None:
    out_dir = tmp_path / "cli_session"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "akta",
            "review",
            "--akta-trigger",
            str(WEAK / "review_trigger.json"),
            "--akta-record",
            str(WEAK / "akta_record.json"),
            "--grant-scope",
            "single_validation_run_draft",
            "--reviewer",
            str(WEAK / "reviewer_protocol_owner.json"),
            "--decision-rationale",
            "Need co-review.",
            "--out-dir",
            str(out_dir),
            "--session",
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Multi-role session required" in result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "session_required"
    validate_artifact(summary, "scope_akta_review_session_summary.schema.json")


def test_akta_review_cli_multi_role_without_session_fails(tmp_path: Path) -> None:
    out_dir = tmp_path / "cli_fail"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "akta",
            "review",
            "--akta-trigger",
            str(WEAK / "review_trigger.json"),
            "--akta-record",
            str(WEAK / "akta_record.json"),
            "--grant-scope",
            "single_validation_run_draft",
            "--reviewer",
            str(WEAK / "reviewer_protocol_owner.json"),
            "--decision-rationale",
            "Solo attempt.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code != 0
    message = str(result.exception or result.output)
    assert "multi-role review session" in message.lower() or "--session" in message


def test_multi_role_session_complete_produces_grant(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    weak = ROOT / "examples" / "weak_evidence_validation_review"
    pilot = ROOT / "examples" / "pilot" / "multi_role_genomics_review"
    out_dir = tmp_path / "complete_out"
    summary = run_akta_review(
        engine,
        akta_record=json.loads((weak / "akta_record.json").read_text(encoding="utf-8")),
        akta_trigger=json.loads((weak / "review_trigger.json").read_text(encoding="utf-8")),
        grant_scope="single_validation_run_draft",
        reviewer=pilot / "reviewer_protocol_owner.json",
        decision_rationale="Session-complete path",
        out_dir=out_dir,
        session_complete=True,
        votes=pilot / "votes.json",
    )
    assert summary["status"] == "completed"
    assert summary["grant_id"].startswith("SCOPE-GRANT-")
    assert (out_dir / "scope_grant.json").exists()
    validate_artifact(summary, "scope_akta_review_summary.schema.json")
