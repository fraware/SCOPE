"""Export PF-Core runtime obligations from SCOPE grants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from scope.hash import verify_hash

SIGNATURE_FIELDS = (
    "grant_signature",
    "signature_algorithm",
    "signed_payload_hash",
    "reviewer_public_key_ref",
)


def export_pf_obligation(grant: dict[str, Any]) -> dict[str, Any]:
    auth = grant.get("authorization", {})
    constraints = grant.get("constraints", {})
    result: dict[str, Any] = {
        "obligation_version": "pf-core-v0.4",
        "grant_id": grant["grant_id"],
        "grant_hash": grant.get("grant_hash"),
        "permitted_tools": auth.get("allowed_tools", []),
        "blocked_tools": auth.get("blocked_tools", []),
        "approved_scope": auth.get("approved_scope"),
        "max_responsibility_level": auth.get("max_responsibility_level"),
        "constraints": {
            "single_use": constraints.get("single_use", False),
            "protocol_version": constraints.get("protocol_version"),
            "requires_pf_core_trace": constraints.get("requires_pf_core_trace", True),
        },
        "expiration": grant.get("expiration", {}),
        "verification_mode": "enforce_at_runtime",
    }
    for field in SIGNATURE_FIELDS:
        if grant.get(field):
            result[field] = grant[field]
    return result


def validate_pf_export(
    obligation: dict[str, Any],
    grant: dict[str, Any],
    schema_path: str | Path | None = None,
) -> None:
    if obligation.get("grant_hash") != grant.get("grant_hash"):
        raise ValueError("PF obligation grant_hash does not match source grant")
    if not verify_hash(grant, "grant_hash"):
        raise ValueError("Source grant hash is invalid (possible tampering)")
    if schema_path:
        with Path(schema_path).open(encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(instance=obligation, schema=schema)
