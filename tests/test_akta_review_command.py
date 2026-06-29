"""Tests for scope akta review CLI command (v0.5.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scope.cli import main
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"


def test_akta_review_command_happy_path(tmp_path):
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
            "Narrow protocol draft approval only.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output

    packet = json.loads((out_dir / "scope_review_packet.json").read_text(encoding="utf-8"))
    decision = json.loads((out_dir / "scope_decision.json").read_text(encoding="utf-8"))
    grant = json.loads((out_dir / "scope_grant.json").read_text(encoding="utf-8"))
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))

    assert packet["packet_id"]
    assert decision["decision"]["approved_scope"] == "protocol_draft"
    assert decision["decision"]["type"] == "approve_narrower_scope"
    assert grant["authorization"]["approved_scope"] == "protocol_draft"
    assert summary["status"] == "completed"
    assert summary["packet_path"].endswith("scope_review_packet.json")
    assert summary["decision_path"].endswith("scope_decision.json")
    assert summary["grant_path"].endswith("scope_grant.json")
    assert summary["approved_scope"] == "protocol_draft"
    assert summary["adapter_contract_version"] == AKTA_REVIEW_CONTRACT_VERSION
    assert summary["identity_assurance_level"] == "IAL0"
    assert "signing_assurance_level" in summary
    assert isinstance(summary["blocked_tools"], list)
    assert summary["scope_trust_root_hash"].startswith("sha256:")


def test_akta_review_rejects_overbroad_grant(tmp_path):
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
            "robot_queue_submission",
            "--reviewer",
            str(EX / "reviewer_protocol_owner.json"),
            "--decision-rationale",
            "Too broad.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code != 0
    assert not (out_dir / "scope_grant.json").exists()


def test_akta_review_engine_refuses_overbroad():
    from scope import ScopeEngine
    from scope.akta_review import run_akta_review

    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    with pytest.raises(ValueError, match="exceeds requested"):
        run_akta_review(
            engine,
            akta_record=EX / "akta_record.json",
            akta_trigger=EX / "review_trigger.json",
            grant_scope="robot_queue_submission",
            reviewer=EX / "reviewer_protocol_owner.json",
            decision_rationale="Too broad.",
            out_dir=EX / "should_not_write",
        )


def test_akta_review_production_requires_signing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
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
            "Production path without key.",
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code != 0
    message = str(result.exception or result.output).lower()
    assert "signing-key" in message or "signed decision" in message
    assert not (out_dir / "scope_grant.json").exists()


def test_akta_review_production_with_signing_key(tmp_path, monkeypatch):
    from scope.signing import Ed25519Signer

    monkeypatch.setenv("SCOPE_PRODUCTION_MODE", "true")
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

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
            "Signed production approval.",
            "--signing-key",
            str(key),
            "--out-dir",
            str(out_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output

    decision = json.loads((out_dir / "scope_decision.json").read_text(encoding="utf-8"))
    grant = json.loads((out_dir / "scope_grant.json").read_text(encoding="utf-8"))
    assert decision.get("decision_signature")
    assert grant["grant_id"].startswith("SCOPE-GRANT-")
    assert decision["provenance"]["scope_trust_root_hash"].startswith("sha256:")
    grant_trust = grant["provenance"]["scope_trust_root_hash"]
    assert grant_trust == decision["provenance"]["scope_trust_root_hash"]
