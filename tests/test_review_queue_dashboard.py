"""Tests for review queue HTML dashboard rendering."""

from __future__ import annotations

from pathlib import Path

from scope import ScopeEngine
from scope.review_queue import ReviewQueue
from scope.review_queue_render import render_queue_dashboard

ROOT = Path(__file__).resolve().parent.parent


def _sample_packet(engine: ScopeEngine) -> dict:
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-DASH", "scientific_action_type": "A5_protocol_modification"}
    return engine.create_packet(record, trigger)


def test_dashboard_renders_workflow_states(tmp_path: Path) -> None:
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _sample_packet(engine)

    needs_info = ReviewQueue.create(packet, persist=False)
    needs_info.assign({"reviewer_id": "r1", "role": "protocol_owner"})
    needs_info.mark_in_review()
    needs_info.mark_needs_information(reason="missing data")
    needs_info.save(tmp_path / "needs_info.json")

    expired = ReviewQueue.create(packet, persist=False)
    expired.expire()
    expired.save(tmp_path / "expired.json")

    escalated = ReviewQueue.create(packet, persist=False)
    escalated.assign({"reviewer_id": "r2", "role": "protocol_owner"})
    escalated.mark_escalated(
        {"reviewer_id": "lead1", "role": "lab_operations_lead"},
        reason="SLA breach",
    )
    escalated.save(tmp_path / "escalated.json")

    html = render_queue_dashboard(tmp_path)
    assert "needs_information" in html
    assert "expired" in html
    assert "escalated" in html
    assert "Status counts:" in html
    assert html.count("needs_information") >= 1
    assert html.count("expired") >= 1
