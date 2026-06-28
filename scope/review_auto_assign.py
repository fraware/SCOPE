"""Auto-assignment of reviewers to review queue entries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scope.errors import ScopeValidationError
from scope.policy import PolicyStore
from scope.review_assignment import resolve_review_assignment


def load_reviewer_assignments(policy_dir: str | Path) -> dict[str, Any]:
    path = Path(policy_dir) / "reviewer_assignments.yaml"
    if not path.exists():
        return {"assignments": {}, "round_robin_from_registry": False}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _registry_reviewer_ids(policy: PolicyStore) -> list[str]:
    return sorted(policy.reviewer_key_registry_entries.keys())


def pick_reviewer_for_role(
    role: str,
    policy: PolicyStore,
    *,
    round_robin_index: int = 0,
) -> dict[str, Any] | None:
    """Pick reviewer_id for a required role from assignments or registry."""
    cfg = load_reviewer_assignments(policy.policy_dir)
    assignments = cfg.get("assignments") or {}
    reviewer_id = assignments.get(role)
    if not reviewer_id and cfg.get("round_robin_from_registry"):
        registry_ids = _registry_reviewer_ids(policy)
        if registry_ids:
            reviewer_id = registry_ids[round_robin_index % len(registry_ids)]
    if not reviewer_id:
        return None
    return {"reviewer_id": str(reviewer_id), "role": role}


def auto_assign(
    packet: dict[str, Any],
    policy: PolicyStore,
) -> dict[str, Any]:
    """Resolve first eligible reviewer from policy assignments or registry."""
    assignment = resolve_review_assignment(packet, policy)
    required_roles = assignment.get("required_roles") or []
    if not required_roles:
        raise ScopeValidationError("No required roles for auto-assignment")

    primary_role = required_roles[0]
    reviewer = pick_reviewer_for_role(primary_role, policy)
    if reviewer is None:
        raise ScopeValidationError(
            f"No reviewer assignment for role {primary_role}; "
            "configure policy/reviewer_assignments.yaml"
        )
    reviewer["auto_assigned"] = True
    reviewer["assignment_context"] = assignment
    return reviewer
