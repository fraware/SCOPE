"""Validate export shapes against documented integration contracts."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export
from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export
from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = Path(__file__).resolve().parent / "fixtures" / "contracts"
SCHEMAS = ROOT / "schemas"
EX = ROOT / "examples" / "protocol_change_review"


def _load_contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_pf_export_matches_contract_shape():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    pf = export_pf_obligation(grant)
    contract = _load_contract("pf_obligation_contract.json")

    for key in contract:
        assert key in pf, f"PF export missing contract field: {key}"
    assert pf["obligation_version"] == contract["obligation_version"]
    assert pf["verification_mode"] == contract["verification_mode"]
    assert isinstance(pf["permitted_tools"], list)
    assert isinstance(pf["blocked_tools"], list)
    validate_pf_export(pf, grant, SCHEMAS / "pf_scope_obligation.schema.json")


def test_pcs_manifest_matches_contract_shape(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    out = export_pcs_artifact(packet, decision, grant, tmp_path / "pcs")
    manifest = json.loads((out / "release_manifest.json").read_text(encoding="utf-8"))
    contract = _load_contract("pcs_manifest_contract.json")

    for key in contract:
        assert key in manifest, f"PCS manifest missing contract field: {key}"
    assert manifest["manifest_version"] == contract["manifest_version"]
    assert set(manifest["artifacts"]) == set(contract["artifacts"])
    for artifact in contract["artifacts"]:
        assert artifact in manifest["hashes"]
        assert manifest["hashes"][artifact].startswith("sha256:")
    for key in contract["source"]:
        assert key in manifest["source"]
    validate_pcs_export(out, SCHEMAS / "pcs_scope_artifact.schema.json")


def test_contract_fixtures_validate_against_schemas():
    pf_contract = _load_contract("pf_obligation_contract.json")
    pcs_contract = _load_contract("pcs_manifest_contract.json")
    pf_schema = json.loads((SCHEMAS / "pf_scope_obligation.schema.json").read_text())
    pcs_schema = json.loads((SCHEMAS / "pcs_scope_artifact.schema.json").read_text())
    jsonschema.validate(instance=pf_contract, schema=pf_schema)
    jsonschema.validate(instance=pcs_contract, schema=pcs_schema)
