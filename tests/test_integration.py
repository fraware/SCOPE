"""Milestone 7 integrated demo: full review-to-authorization pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from adapters.pcs.export_artifact import export_pcs_artifact
from adapters.pf_core.export_obligation import export_pf_obligation
from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_milestone7_integrated_demo(tmp_path):
    """Section 26/32 proof-of-life with PF-Core, PCS, and quality reporting."""
    ledger_path = tmp_path / "scope_events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger_path)

    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    assert packet["review_request"]["required_review_roles"] == ["protocol_owner"]
    assert packet["review_request"]["akta_admissibility"] == "review_required"
    engine.validate_packet(packet)

    decision = engine.submit_decision(
        packet,
        json.loads((EX / "reviewer_protocol_owner.json").read_text(encoding="utf-8")),
        json.loads((EX / "decision.json").read_text(encoding="utf-8")),
    )
    assert decision["decision"]["approved_scope"] == "protocol_draft"

    grant = engine.issue_grant(packet, decision)
    ctx = json.loads((EX / "current_context.json").read_text(encoding="utf-8"))

    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert not engine.check_grant(grant, "robot_queue.submit", ctx)
    assert not engine.check_grant(
        grant,
        "protocol_editor.draft_change",
        {**ctx, "protocol_version": "protocol_v4"},
    )

    pf = export_pf_obligation(grant)
    assert pf["permitted_tools"] == ["protocol_editor.draft_change"]
    assert "robot_queue.submit" in pf["blocked_tools"]
    assert pf["verification_mode"] == "enforce_at_runtime"

    pcs_dir = export_pcs_artifact(packet, decision, grant, tmp_path / "pcs")
    assert (pcs_dir / "release_manifest.json").exists()
    manifest = json.loads((pcs_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["artifacts"]) == {
        "scope_packet.json",
        "scope_decision.json",
        "scope_grant.json",
        "pf_obligation.json",
    }
    assert all(v.startswith("sha256:") for v in manifest["hashes"].values())

    report = engine.quality_report()
    assert "metrics" in report
    assert report["event_counts"].get("packet_created", 0) >= 1
    assert report["event_counts"].get("grant_issued", 0) >= 1
