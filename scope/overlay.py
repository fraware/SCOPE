"""Domain overlay validation and listing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scope.errors import ScopeValidationError
from scope.schema_util import validate_artifact


def load_overlay(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def validate_overlay_structure(overlay: dict[str, Any]) -> None:
    """Validate overlay YAML against domain overlay schema."""
    validate_artifact(overlay, "domain_overlay.schema.json")
    overlay_id = overlay.get("overlay_id")
    if not overlay_id:
        raise ScopeValidationError("Overlay missing overlay_id")
    overrides = overlay.get("matrix_overrides")
    if overrides is not None and not isinstance(overrides, dict):
        raise ScopeValidationError("matrix_overrides must be a mapping")


def validate_overlay_file(path: str | Path) -> dict[str, Any]:
    overlay = load_overlay(path)
    validate_overlay_structure(overlay)
    return {
        "path": str(path),
        "overlay_id": overlay.get("overlay_id"),
        "version": overlay.get("version"),
        "valid": True,
    }


def list_overlays(policy_dir: str | Path) -> list[dict[str, Any]]:
    overlay_dir = Path(policy_dir) / "domain_overlays"
    if not overlay_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(overlay_dir.glob("*.yaml")):
        overlay = load_overlay(path)
        results.append(
            {
                "path": str(path),
                "overlay_id": overlay.get("overlay_id"),
                "version": overlay.get("version"),
                "description": overlay.get("description"),
            }
        )
    return results
