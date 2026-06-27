"""Export PF-Core runtime obligations from SCOPE grants."""

from __future__ import annotations

from typing import Any


def export_pf_obligation(grant: dict[str, Any]) -> dict[str, Any]:
    auth = grant.get("authorization", {})
    constraints = grant.get("constraints", {})
    return {
        "obligation_version": "pf-core-v0.1",
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
