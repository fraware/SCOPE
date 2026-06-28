"""Live PF/PCS contract validation when sibling repos are present (SCOPE-5)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.external_contracts import (
    PCS_CORE_REPO_ENV,
    PF_CORE_REPO_ENV,
    validate_pcs_export_live,
    validate_pf_export_live,
)

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_pf_live_validation_skips_without_repo():
    ok, message = validate_pf_export_live({}, {})
    assert ok is False
    assert message.startswith("Skipped:")
    assert PF_CORE_REPO_ENV in message
    assert "PF-Core" in message or "pf" in message.lower()


def test_pcs_live_validation_skips_without_repo(tmp_path):
    ok, message = validate_pcs_export_live(tmp_path)
    assert ok is False
    assert message.startswith("Skipped:")
    assert PCS_CORE_REPO_ENV in message
    assert "PCS" in message or "pcs" in message.lower()


@pytest.mark.live_contract
def test_pf_live_validation_when_repo_present(tmp_path):
    repo = os.environ.get(PF_CORE_REPO_ENV)
    if not repo or not Path(repo).is_dir():
        pytest.skip(f"{PF_CORE_REPO_ENV} not set or path missing")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    from adapters.pf_core.export_obligation import export_pf_obligation

    pf = export_pf_obligation(grant)
    ok, message = validate_pf_export_live(pf, grant, tmp_dir=tmp_path / "pf")
    if "no PF validator found" in message:
        pytest.skip(message)
    assert ok, message


@pytest.mark.live_contract
def test_pcs_live_validation_when_repo_present(tmp_path):
    repo = os.environ.get(PCS_CORE_REPO_ENV)
    if not repo or not Path(repo).is_dir():
        pytest.skip(f"{PCS_CORE_REPO_ENV} not set or path missing")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    from adapters.pcs.export_artifact import export_pcs_artifact

    out = export_pcs_artifact(packet, decision, grant, tmp_path / "pcs")
    ok, message = validate_pcs_export_live(out)
    if "no PCS validator found" in message:
        pytest.skip(message)
    assert ok, message
