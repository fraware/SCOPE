"""Tests for packet render (Priority 8)."""

from pathlib import Path

from scope import ScopeEngine
from scope.render import render_html, render_markdown

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"


def test_render_markdown_contains_sections():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    md = render_markdown(packet, engine.policy)
    assert "# SCOPE Review Packet" in md
    assert "## Requested Action" in md
    assert "## Required Reviewers" in md
    assert "## Scientific Context" in md
    assert "## AKTA Constraints" in md
    assert "## Approval Permits" in md
    assert "## Approval Does NOT Permit" in md
    assert "## Reviewer Checklist" in md
    assert "does not constitute" in md.lower()
    assert packet["review_request"]["requested_scope"] in md
    assert "Review route:" in md
    assert "Blocked Tools (severity)" in md
    assert "high severity" in md
    assert "robot_queue.submit" in md
    assert "Confirm your role is one of:" in md
    assert "Declare conflicts of interest" in md


def test_render_markdown_evidence_and_akta_reason():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "akta_decision_reason": "Weak evidence requires explicit scope narrowing",
        "scientific_context": {
            "evidence_state": "E0_unknown",
            "validation_status": "V0_unknown",
        },
    }
    record = {"record_id": "AKTA-RENDER-WARN", "scientific_action_type": "A6_experimental_planning"}
    packet = engine.create_packet(record, trigger)
    md = render_markdown(packet, engine.policy)
    assert "## Evidence and Validation Warnings" in md
    assert "E0_unknown" in md
    assert "V0_unknown" in md
    assert "## AKTA Decision Reason" in md
    assert "Weak evidence requires explicit scope narrowing" in md
    assert "## Approval Scope Context" in md


def test_render_html_contains_sections():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    html = render_html(packet)
    assert "<h1>" in html
    assert "Requested Action" in html
    assert "certification" in html.lower()
