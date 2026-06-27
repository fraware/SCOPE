"""Policy loading and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import yaml

from scope.errors import PolicyError
from scope.hash import canonical_json


class PolicyStore:
    """Loads and exposes SCOPE policy YAML files."""

    POLICY_FILES = (
        "reviewer_roles.yaml",
        "role_to_action_matrix.yaml",
        "approval_scopes.yaml",
        "scope_to_tool_matrix.yaml",
        "expiration_rules.yaml",
        "decision_options.yaml",
        "quality_metrics.yaml",
    )

    def __init__(self, policy_dir: Path) -> None:
        self.policy_dir = Path(policy_dir)
        if not self.policy_dir.is_dir():
            raise PolicyError(f"Policy directory not found: {self.policy_dir}")
        self._data: dict[str, Any] = {}
        for name in self.POLICY_FILES:
            path = self.policy_dir / name
            if not path.exists():
                raise PolicyError(f"Missing policy file: {path}")
            with path.open(encoding="utf-8") as fh:
                self._data[name] = yaml.safe_load(fh)
        self.version = self._data["reviewer_roles.yaml"].get("version", "unknown")
        self.policy_hash = self._compute_policy_hash()

    def _compute_policy_hash(self) -> str:
        digest = hashlib.sha256(canonical_json(self._data).encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @classmethod
    def from_dir(cls, policy_dir: str | Path) -> PolicyStore:
        return cls(Path(policy_dir))

    @property
    def reviewer_roles(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["reviewer_roles.yaml"]["roles"])

    @property
    def role_matrix(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["role_to_action_matrix.yaml"]["matrix"])

    @property
    def scope_hierarchy(self) -> list[str]:
        return cast(list[str], self._data["approval_scopes.yaml"]["hierarchy"])

    @property
    def scope_semantics(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["approval_scopes.yaml"]["semantics"])

    @property
    def scope_tools(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["scope_to_tool_matrix.yaml"]["scopes"])

    @property
    def expiration_rules(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["expiration_rules.yaml"])

    @property
    def decision_options(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["decision_options.yaml"])

    @property
    def quality_metrics(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["quality_metrics.yaml"])

    def get_required_roles(self, action_type: str) -> list[str]:
        entry = self.role_matrix.get(action_type)
        if not entry:
            raise PolicyError(f"Unknown action type: {action_type}")
        return list(entry.get("required_roles", []))

    def role_can_approve_scope(self, role: str, scope: str) -> bool:
        role_def = self.reviewer_roles.get(role)
        if not role_def:
            return False
        return scope in role_def.get("can_approve_scopes", [])

    def get_scope_tools(self, scope: str) -> dict[str, Any]:
        entry = self.scope_tools.get(scope)
        if not entry:
            raise PolicyError(f"Unknown approval scope: {scope}")
        return cast(dict[str, Any], entry)

    def get_default_expiration(self, scope: str) -> list[str]:
        defaults = self.expiration_rules.get("default_expiration", {})
        entry = defaults.get(scope, defaults.get("default", {}))
        return list(entry.get("expires_after", ["policy_version_change"]))

    def allowed_decisions(self, action_type: str) -> list[str]:
        by_action = self.decision_options.get("allowed_by_action", {})
        return list(by_action.get(action_type, by_action.get("default", [])))

    def is_approval_decision(self, decision_type: str) -> bool:
        return decision_type in self.decision_options.get("approval_decisions", [])
