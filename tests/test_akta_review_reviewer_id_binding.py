"""Tests for --reviewer-id binding in akta review (SCOPE-2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from scope import ScopeEngine
from scope.akta_review import run_akta_review
from scope.cli import main
from scope.errors import ScopeValidationError
from scope.key_registry import register_reviewer_key
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def _policy_with_registry_signer(tmp_path: Path) -> tuple[Path, Path]:
    policy_dir = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_dir)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    register_reviewer_key(policy_dir, "reviewer_001", pub)
    registry_path = policy_dir / "reviewer_key_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["reviewers"]["reviewer_001"]["signing_key_path"] = str(key)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return policy_dir, key


def test_reviewer_id_mismatch_fails(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    with pytest.raises(ScopeValidationError, match="does not match reviewer artifact"):
        run_akta_review(
            engine,
            akta_record=EX / "akta_record.json",
            akta_trigger=EX / "review_trigger.json",
            grant_scope="protocol_draft",
            reviewer=EX / "reviewer_protocol_owner.json",
            decision_rationale="mismatch test",
            out_dir=tmp_path / "out",
            reviewer_id="wrong_reviewer_id",
        )


def test_reviewer_id_passed_to_registry_signing(tmp_path: Path) -> None:
    policy_dir, _key = _policy_with_registry_signer(tmp_path)
    engine = ScopeEngine.from_policy_dir(policy_dir)
    out_dir = tmp_path / "signed_out"
    summary = run_akta_review(
        engine,
        akta_record=EX / "akta_record.json",
        akta_trigger=EX / "review_trigger.json",
        grant_scope="protocol_draft",
        reviewer=EX / "reviewer_protocol_owner.json",
        decision_rationale="registry signing",
        out_dir=out_dir,
        signing_provider="registry",
        reviewer_id="reviewer_001",
    )
    assert summary["status"] == "completed"
    decision = json.loads((out_dir / "scope_decision.json").read_text(encoding="utf-8"))
    assert decision.get("decision_signature")
    assert decision["reviewer"]["reviewer_id"] == "reviewer_001"


def test_cli_passes_reviewer_id_to_run(tmp_path: Path) -> None:
    policy_dir, _key = _policy_with_registry_signer(tmp_path)
    out_dir = tmp_path / "cli_out"
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
            "CLI registry path.",
            "--out-dir",
            str(out_dir),
            "--signing-provider",
            "registry",
            "--reviewer-id",
            "reviewer_001",
            "--policy",
            str(policy_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    decision = json.loads((out_dir / "scope_decision.json").read_text(encoding="utf-8"))
    assert decision.get("decision_signature")


def test_registry_uses_artifact_reviewer_id_without_cli_flag(tmp_path: Path) -> None:
    policy_dir, _key = _policy_with_registry_signer(tmp_path)
    engine = ScopeEngine.from_policy_dir(policy_dir)
    with pytest.raises(ScopeValidationError, match="No registry entry"):
        run_akta_review(
            engine,
            akta_record=EX / "akta_record.json",
            akta_trigger=EX / "review_trigger.json",
            grant_scope="protocol_draft",
            reviewer={"reviewer_id": "unknown_reviewer", "role": "protocol_owner"},
            decision_rationale="no registry entry",
            out_dir=tmp_path / "out",
            signing_provider="registry",
        )
