"""Policy loading and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import yaml

from scope.errors import PolicyError
from scope.hash import canonical_json, scope_trust_root_hash


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
        "blocked_tool_severity.yaml",
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
        self._domain_overlays = self._load_domain_overlays()
        self._reviewer_key_registry = self._load_reviewer_key_registry()
        self.version = self._data["reviewer_roles.yaml"].get("version", "unknown")
        self.policy_hash = self._compute_policy_hash()

    def _load_domain_overlays(self) -> dict[str, Any]:
        overlays: dict[str, Any] = {}
        overlay_dir = self.policy_dir / "domain_overlays"
        if not overlay_dir.is_dir():
            return overlays
        for path in sorted(overlay_dir.glob("*.yaml")):
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            overlay_id = data.get("overlay_id")
            if overlay_id:
                overlays[str(overlay_id)] = data
        return overlays

    def _load_reviewer_key_registry(self) -> dict[str, Any]:
        path = self.policy_dir / "reviewer_key_registry.yaml"
        if not path.exists():
            return {"reviewers": {}}
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {"reviewers": {}}

    def _compute_policy_hash(self) -> str:
        digest_input = dict(self._data)
        digest_input["_domain_overlays"] = self._domain_overlays
        digest = hashlib.sha256(canonical_json(digest_input).encode("utf-8")).hexdigest()
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

    @property
    def blocked_tool_severity(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._data["blocked_tool_severity.yaml"])

    @property
    def domain_overlays(self) -> dict[str, Any]:
        return dict(self._domain_overlays)

    @property
    def reviewer_key_registry(self) -> dict[str, str]:
        reviewers = self._reviewer_key_registry.get("reviewers") or {}
        result: dict[str, str] = {}
        for reviewer_id, entry in reviewers.items():
            if isinstance(entry, dict):
                ref = entry.get("public_key_ref")
                if ref:
                    result[str(reviewer_id)] = str(ref)
            elif entry:
                result[str(reviewer_id)] = str(entry)
        return result

    @property
    def reviewer_key_registry_entries(self) -> dict[str, dict[str, Any]]:
        reviewers = self._reviewer_key_registry.get("reviewers") or {}
        entries: dict[str, dict[str, Any]] = {}
        for reviewer_id, entry in reviewers.items():
            if isinstance(entry, dict):
                entries[str(reviewer_id)] = dict(entry)
            else:
                entries[str(reviewer_id)] = {"public_key_ref": str(entry)}
        return entries

    @property
    def reviewer_key_registry_version(self) -> str:
        return str(self._reviewer_key_registry.get("version", "unknown"))

    @property
    def reviewer_key_registry_hash(self) -> str:
        digest = hashlib.sha256(
            canonical_json(self._reviewer_key_registry).encode("utf-8")
        ).hexdigest()
        return f"sha256:{digest}"

    @property
    def scope_trust_root_hash(self) -> str:
        return scope_trust_root_hash(self.policy_hash, self.reviewer_key_registry_hash)

    def get_domain_overlay(self, overlay_id: str | None) -> dict[str, Any] | None:
        if not overlay_id:
            return None
        return self._domain_overlays.get(str(overlay_id))

    def get_matrix_entry(
        self,
        action_type: str,
        *,
        domain_overlay: str | None = None,
    ) -> dict[str, Any]:
        overlay = self.get_domain_overlay(domain_overlay)
        if overlay:
            overrides = overlay.get("matrix_overrides") or {}
            if action_type in overrides:
                base = dict(self.role_matrix.get(action_type, {}))
                base.update(overrides[action_type])
                return base
        entry = self.role_matrix.get(action_type)
        if not entry:
            raise PolicyError(f"Unknown action type: {action_type}")
        return dict(entry)

    def get_required_roles(
        self,
        action_type: str,
        *,
        domain_overlay: str | None = None,
    ) -> list[str]:
        entry = self.get_matrix_entry(action_type, domain_overlay=domain_overlay)
        return list(entry.get("required_roles", []))

    def requires_multi_reviewer_session(
        self,
        action_type: str,
        *,
        domain_overlay: str | None = None,
    ) -> bool:
        entry = self.get_matrix_entry(action_type, domain_overlay=domain_overlay)
        required = entry.get("required_roles", [])
        if entry.get("require_all") and len(required) > 1:
            return True
        return False

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

    def scope_requires_roles(self, scope: str) -> list[str]:
        return list(self.get_scope_tools(scope).get("requires_roles", []))

    def get_default_expiration(self, scope: str) -> list[str]:
        defaults = self.expiration_rules.get("default_expiration", {})
        entry = defaults.get(scope, defaults.get("default", {}))
        return list(entry.get("expires_after", ["policy_version_change"]))

    def allowed_decisions(self, action_type: str) -> list[str]:
        by_action = self.decision_options.get("allowed_by_action", {})
        return list(by_action.get(action_type, by_action.get("default", [])))

    def is_approval_decision(self, decision_type: str) -> bool:
        return decision_type in self.decision_options.get("approval_decisions", [])
