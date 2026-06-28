"""Tests for domain overlay tooling."""

from __future__ import annotations

from scope.overlay import list_overlays, validate_overlay_file


def test_list_overlays_includes_genomics() -> None:
    overlays = list_overlays("policy/")
    ids = {o["overlay_id"] for o in overlays}
    assert "genomics_research" in ids
    assert "clinical_research" in ids


def test_validate_genomics_overlay() -> None:
    result = validate_overlay_file("policy/domain_overlays/genomics_research.yaml")
    assert result["valid"] is True
