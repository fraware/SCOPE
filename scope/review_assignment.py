"""Review assignment resolution from role matrix and packet context."""

from __future__ import annotations

from typing import Any

from scope.policy import PolicyStore


def resolve_review_assignment(
    packet: dict[str, Any],
    policy: PolicyStore,
) -> dict[str, Any]:
    """Resolve required roles and quorum mode for a packet."""
    action_type = packet["review_request"]["scientific_action_type"]
    domain_overlay = packet.get("scientific_context", {}).get("domain_overlay")
    required_roles = policy.get_required_roles(action_type, domain_overlay=domain_overlay)
    entry = policy.get_matrix_entry(action_type, domain_overlay=domain_overlay)
    mode = "require_all"
    if entry.get("require_any"):
        mode = "require_any"
    elif entry.get("require_all"):
        mode = "require_all"
    return {
        "action_type": action_type,
        "required_roles": required_roles,
        "quorum_mode": mode,
        "domain_overlay": domain_overlay,
        "packet_id": packet["packet_id"],
    }
