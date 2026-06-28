"""Tests for VSA adapter."""

from pathlib import Path

from adapters.vsa.import_report import import_vsa_report
from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "adapters" / "vsa" / "examples" / "scientific_report_example.json"


def test_import_vsa_report_example():
    summary = import_vsa_report(EXAMPLE)
    assert summary["source"] == "vsa_scientific_report"
    assert summary["report_id"] == "VSA-EXAMPLE-001"
    assert len(summary["claim_warnings"]) >= 1
    assert summary["evidence_summary"]["overall_state"] == "E2_preliminary"


def test_vsa_report_in_packet():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-VSA", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger, vsa_report=EXAMPLE)
    vsa = packet["review_artifacts"]["vsa_report"]
    assert vsa["report_id"] == "VSA-EXAMPLE-001"
