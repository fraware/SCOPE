"""Tests for hardened PF/PCS exports (Priority 7)."""

import json
from pathlib import Path

import pytest

from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export
from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export
from scope import ScopeEngine
from scope.hash import compute_hash

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"
SCHEMAS = ROOT / "schemas"


def test_pf_export_validate():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    pf = export_pf_obligation(grant)
    validate_pf_export(pf, grant, SCHEMAS / "pf_scope_obligation.schema.json")
    assert pf["obligation_version"] == "pf-core-v0.4"


def test_pcs_export_validate(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    out = export_pcs_artifact(packet, decision, grant, tmp_path / "pcs")
    validate_pcs_export(out, SCHEMAS / "pcs_scope_artifact.schema.json")
    manifest = json.loads((out / "release_manifest.json").read_text())
    assert manifest["manifest_version"] == "pcs-v0.4"


def test_tampered_grant_fails_validation(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    out = export_pcs_artifact(packet, decision, grant, tmp_path / "pcs")
    tampered = json.loads((out / "scope_grant.json").read_text())
    tampered["authorization"]["allowed_tools"].append("robot_queue.submit")
    tampered["grant_hash"] = compute_hash(tampered, field_name="grant_hash")
    with (out / "scope_grant.json").open("w", encoding="utf-8") as fh:
        json.dump(tampered, fh, indent=2, sort_keys=True)
    with pytest.raises(ValueError, match="Hash mismatch|invalid"):
        validate_pcs_export(out)
