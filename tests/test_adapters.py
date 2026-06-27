"""Tests for export adapters."""

import json
from pathlib import Path

from adapters.pcs.export_artifact import export_pcs_artifact
from adapters.pf_core.export_obligation import export_pf_obligation
from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_pf_export():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        json.loads((EX / "reviewer_protocol_owner.json").read_text()),
        json.loads((EX / "decision.json").read_text()),
    )
    grant = engine.issue_grant(packet, decision)
    pf = export_pf_obligation(grant)
    assert "protocol_editor.draft_change" in pf["permitted_tools"]
    assert "robot_queue.submit" in pf["blocked_tools"]


def test_pcs_export(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        json.loads((EX / "reviewer_protocol_owner.json").read_text()),
        json.loads((EX / "decision.json").read_text()),
    )
    grant = engine.issue_grant(packet, decision)
    out = export_pcs_artifact(packet, decision, grant, tmp_path)
    assert (out / "release_manifest.json").exists()
    assert (out / "scope_grant.json").exists()


def test_end_to_end_demo():
    """Proof-of-life: section 26 protocol modification demo."""
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    assert packet["review_request"]["akta_admissibility"] == "review_required"

    decision = engine.submit_decision(
        packet,
        json.loads((EX / "reviewer_protocol_owner.json").read_text()),
        json.loads((EX / "decision.json").read_text()),
    )
    grant = engine.issue_grant(packet, decision)

    ctx = json.loads((EX / "current_context.json").read_text())
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert not engine.check_grant(grant, "robot_queue.submit", ctx)

    stale = dict(ctx, protocol_version="protocol_v4")
    assert not engine.check_grant(grant, "protocol_editor.draft_change", stale)

    pf = export_pf_obligation(grant)
    assert pf["permitted_tools"] == ["protocol_editor.draft_change"]
