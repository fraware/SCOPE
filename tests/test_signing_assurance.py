"""Tests for signing assurance levels."""

from __future__ import annotations

from pathlib import Path

import pytest

from scope.errors import GrantValidationError, ScopeValidationError
from scope.signing_assurance import (
    SAL0,
    SAL1,
    SAL2,
    HsmKmsSigningProvider,
    check_minimum_signing_assurance,
    load_minimum_signing_assurance,
    resolve_signing_assurance_level,
)

ROOT = Path(__file__).resolve().parent.parent


def test_sal0_unsigned() -> None:
    assert resolve_signing_assurance_level({"decision_id": "D1"}) == SAL0


def test_sal1_local_signature() -> None:
    artifact = {
        "decision_id": "D1",
        "decision_signature": "abc",
        "reviewer_public_key_ref": "reviewer1.pub",
    }
    level = resolve_signing_assurance_level(artifact, provider_name="local_pem")
    assert level in (SAL0, SAL1)


def test_sal2_env_provider() -> None:
    artifact = {"decision_id": "D1", "decision_signature": "abc"}
    level = resolve_signing_assurance_level(artifact, provider_name="env_key")
    assert level == SAL2


def test_minimum_signing_enforced_in_production(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policy"
    policy_dir.mkdir()
    cfg = ROOT / "policy" / "minimum_signing_assurance.yaml"
    (policy_dir / "minimum_signing_assurance.yaml").write_text(
        cfg.read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(GrantValidationError, match="Signing assurance"):
        check_minimum_signing_assurance(
            SAL0,
            policy_dir,
            approved_scope="robot_queue_submission",
            production=True,
        )


def test_minimum_policy_loaded() -> None:
    cfg = load_minimum_signing_assurance(ROOT / "policy")
    assert cfg.get("minimum_level") == "SAL1"
    assert "robot_queue_submission" in cfg.get("high_risk_scopes", [])


def test_hsm_provider_is_external_stub() -> None:
    provider = HsmKmsSigningProvider()
    with pytest.raises(ScopeValidationError, match="KMS"):
        provider.get_signer()
