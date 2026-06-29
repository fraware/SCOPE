"""Import SCIM/LDAP directory snapshots into org RBAC membership."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml

from scope.errors import ScopeValidationError


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_snapshot(path: Path, source: str) -> dict[str, Any]:
    if not path.is_file():
        raise ScopeValidationError(f"RBAC sync source file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        if source == "ldap":
            return cast(dict[str, Any], json.load(fh))
        if path.suffix in (".json",):
            return cast(dict[str, Any], json.load(fh))
        return cast(dict[str, Any], yaml.safe_load(fh) or {})


def _filter_active_delegations(delegations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    for delegation in delegations:
        valid_until = delegation.get("valid_until")
        if valid_until:
            try:
                if now > _parse_ts(str(valid_until)):
                    continue
            except ValueError:
                continue
        active.append(delegation)
    return active


def build_org_rbac_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Convert SCIM or LDAP JSON snapshot to org_rbac.yaml structure."""
    org_units: dict[str, Any] = {}
    for user in snapshot.get("users") or []:
        if user.get("active") is False:
            continue
        reviewer_id = str(user.get("id") or user.get("userName", ""))
        org_unit = str(user.get("org_unit") or "default")
        roles = [str(r) for r in (user.get("roles") or [])]
        if not reviewer_id or not roles:
            continue
        unit = org_units.setdefault(org_unit, {"members": {}})
        unit["members"][reviewer_id] = {"roles": roles}

    for group in snapshot.get("groups") or []:
        group_roles = group.get("roles") or []
        for member in group.get("members") or []:
            reviewer_id = str(member)
            org_unit = str(group.get("org_unit") or "default")
            unit = org_units.setdefault(org_unit, {"members": {}})
            entry = unit["members"].setdefault(reviewer_id, {"roles": []})
            for role in group_roles:
                if role not in entry["roles"]:
                    entry["roles"].append(str(role))

    delegations = _filter_active_delegations(list(snapshot.get("delegations") or []))
    role_permissions = snapshot.get("role_permissions") or {}
    version = str(snapshot.get("version") or "scope-core-v0.10")
    return {
        "version": version,
        "org_units": org_units,
        "delegations": delegations,
        "role_permissions": role_permissions,
    }


def sync_rbac(
    *,
    source: str,
    file_path: str | Path,
    policy_dir: str | Path,
    out_path: str | Path | None = None,
) -> Path:
    """Import snapshot and write org_rbac.yaml."""
    normalized = source.lower()
    if normalized not in ("scim", "ldap"):
        raise ScopeValidationError(f"Unsupported RBAC sync source: {source}")

    snapshot = _load_snapshot(Path(file_path), normalized)
    org_rbac = build_org_rbac_from_snapshot(snapshot)
    target = Path(out_path) if out_path else Path(policy_dir) / "org_rbac.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(org_rbac, fh, sort_keys=False, default_flow_style=False)
    return target
