"""Institutional RBAC with org units and delegation chains."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scope.errors import ScopeValidationError


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_org_rbac(policy_dir: str | Path) -> dict[str, Any]:
    path = Path(policy_dir) / "org_rbac.yaml"
    if not path.exists():
        return {"org_units": {}, "delegations": [], "role_permissions": {}}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _member_roles(org_rbac: dict[str, Any], reviewer_id: str) -> set[str]:
    roles: set[str] = set()
    for unit in (org_rbac.get("org_units") or {}).values():
        members = (unit or {}).get("members") or {}
        entry = members.get(reviewer_id)
        if entry:
            roles.update(str(r) for r in entry.get("roles") or [])
    return roles


def _active_delegations(
    org_rbac: dict[str, Any],
    reviewer_id: str,
    *,
    at: datetime | None = None,
) -> list[dict[str, Any]]:
    current = at or datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    for delegation in org_rbac.get("delegations") or []:
        if str(delegation.get("granted_to")) != reviewer_id:
            continue
        valid_until = delegation.get("valid_until")
        if valid_until:
            try:
                if current > _parse_ts(str(valid_until)):
                    continue
            except ValueError:
                continue
        active.append(delegation)
    return active


def resolve_effective_roles(
    reviewer_id: str,
    policy_dir: str | Path,
    *,
    at: datetime | None = None,
) -> set[str]:
    """Return direct and delegated roles for a reviewer at a timestamp."""
    org_rbac = load_org_rbac(policy_dir)
    roles = _member_roles(org_rbac, reviewer_id)
    for delegation in _active_delegations(org_rbac, reviewer_id, at=at):
        role = delegation.get("role")
        if role:
            roles.add(str(role))
    return roles


def check_rbac_permission(
    reviewer_id: str,
    role: str,
    action: str,
    policy_dir: str | Path,
    *,
    at: datetime | None = None,
) -> None:
    """Raise ScopeValidationError when reviewer lacks RBAC permission for action."""
    org_rbac = load_org_rbac(policy_dir)
    effective = resolve_effective_roles(reviewer_id, policy_dir, at=at)
    if role not in effective:
        raise ScopeValidationError(
            f"RBAC: reviewer {reviewer_id} lacks effective role {role} "
            f"(has {sorted(effective)})"
        )
    permissions = (org_rbac.get("role_permissions") or {}).get(role) or {}
    flag = f"can_{action}"
    if permissions and not permissions.get(flag, True):
        raise ScopeValidationError(f"RBAC: role {role} cannot {action}")


def enforce_rbac_enabled() -> bool:
    import os

    value = os.environ.get("SCOPE_ENFORCE_RBAC", "").lower()
    return value in ("1", "true", "yes")
