"""Full AKTA to SCOPE to PF to PCS chain integration test."""

import json
from pathlib import Path

from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export
from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export
from scope import ScopeEngine
from scope.render import render_markdown

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"
SCHEMAS = ROOT / "schemas"


def test_full_akta_scope_pf_pcs_chain(tmp_path):
    ledger_path = tmp_path / "scope_events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger_path)

    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    assert packet["review_request"]["requested_scope"] == "protocol_draft"
    assert packet["review_request"]["scope_inference_source"] == "akta_trigger"

    md = render_markdown(packet)
    assert "protocol_draft" in md

    decision = engine.submit_decision(
        packet,
        json.loads((EX / "reviewer_protocol_owner.json").read_text()),
        json.loads((EX / "decision.json").read_text()),
    )
    grant = engine.issue_grant(packet, decision)
    ctx = json.loads((EX / "current_context.json").read_text())

    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert not engine.check_grant(grant, "robot_queue.submit", ctx)
    assert not engine.check_grant(
        grant, "protocol_editor.draft_change", {**ctx, "protocol_version": "protocol_v4"}
    )

    pf = export_pf_obligation(grant)
    validate_pf_export(pf, grant, SCHEMAS / "pf_scope_obligation.schema.json")
    assert "protocol_editor.draft_change" in pf["permitted_tools"]

    pcs_dir = export_pcs_artifact(
        packet,
        decision,
        grant,
        tmp_path / "pcs",
        ledger_events=engine.ledger.events(),
        quality_warnings=engine.quality_report().get("warnings", []),
    )
    validate_pcs_export(pcs_dir, SCHEMAS / "pcs_scope_artifact.schema.json")

    report = engine.quality_report()
    assert report["report_version"] == "0.2"
    assert report["summary"]["total_grants"] >= 1
    assert "by_reviewer" in report
