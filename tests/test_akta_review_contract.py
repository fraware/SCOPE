"""Tests for frozen AKTA review output contract."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scope.cli import main
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION
from scope.schema_util import validate_artifact

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"


def test_summary_schema_fields() -> None:
    summary = {
        "packet_path": "/out/scope_review_packet.json",
        "decision_path": "/out/scope_decision.json",
        "grant_path": "/out/scope_grant.json",
        "approved_scope": "protocol_draft",
        "requested_scope": "protocol_draft",
        "adapter_contract_version": AKTA_REVIEW_CONTRACT_VERSION,
        "identity_assurance_level": "IAL0",
        "signing_assurance_level": "SAL0",
    }
    validate_artifact(summary, "scope_akta_review_summary.schema.json")


def test_akta_review_summary_contract(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "akta",
            "review",
            "--akta-trigger",
            str(EX / "review_trigger.json"),
            "--akta-record",
            str(EX / "akta_record.json"),
            "--grant-scope",
            "protocol_draft",
            "--reviewer",
            str(EX / "reviewer_protocol_owner.json"),
            "--decision-rationale",
            "Contract test.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    validate_artifact(summary, "scope_akta_review_summary.schema.json")
    assert summary["adapter_contract_version"] == AKTA_REVIEW_CONTRACT_VERSION
    assert summary["identity_assurance_level"] == "IAL0"
    assert "signing_assurance_level" in summary
    assert (out_dir / "scope_review_packet.json").is_file()
    assert (out_dir / "scope_decision.json").is_file()
    assert (out_dir / "scope_grant.json").is_file()


def test_akta_review_unsigned_production_fails(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "akta",
            "review",
            "--akta-trigger",
            str(EX / "review_trigger.json"),
            "--akta-record",
            str(EX / "akta_record.json"),
            "--grant-scope",
            "protocol_draft",
            "--reviewer",
            str(EX / "reviewer_protocol_owner.json"),
            "--decision-rationale",
            "Should fail.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
        env={"SCOPE_PRODUCTION_MODE": "true"},
    )
    assert result.exit_code != 0
