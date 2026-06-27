"""Tests for packet render (Priority 8)."""

from pathlib import Path

from scope import ScopeEngine
from scope.render import render_html, render_markdown

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_drift"


def test_render_markdown_contains_sections():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    md = render_markdown(packet)
    assert "# SCOPE Review Packet" in md
    assert "## Requested Action" in md
    assert "## Required Reviewers" in md
    assert "## Scientific Context" in md
    assert "## AKTA Constraints" in md
    assert "does not constitute" in md.lower()
    assert packet["review_request"]["requested_scope"] in md


def test_render_html_contains_sections():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    html = render_html(packet)
    assert "<h1>" in html
    assert "Requested Action" in html
    assert "certification" in html.lower()
