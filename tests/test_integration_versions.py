"""Tests for integration version constants."""

from __future__ import annotations

from scope.integration_versions import PCS_MANIFEST_VERSION, PF_CORE_VERSION


def test_pf_pcs_versions_v06() -> None:
    assert PF_CORE_VERSION == "pf-core-v0.5"
    assert PCS_MANIFEST_VERSION == "pcs-v0.5"
