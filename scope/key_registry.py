"""Reviewer public key registry workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scope.errors import ScopeValidationError
from scope.policy import PolicyStore
from scope.signing import Ed25519PublicVerifier, verify_artifact_signature

_LEGACY_PRIVATE_KEY_FIELDS = frozenset({"private_key_file", "private_key_path"})


def _sanitize_reviewer_entry(entry: Any) -> tuple[Any, list[str]]:
    """Strip legacy private key fields from a registry reviewer entry."""
    if not isinstance(entry, dict):
        return entry, []
    removed = [field for field in _LEGACY_PRIVATE_KEY_FIELDS if field in entry]
    if not removed:
        return entry, []
    cleaned = {key: value for key, value in entry.items() if key not in _LEGACY_PRIVATE_KEY_FIELDS}
    return cleaned, removed


def _sanitize_registry_data(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Return registry copy with private key fields removed from reviewer entries."""
    sanitized = dict(data)
    reviewers = sanitized.get("reviewers") or {}
    cleaned_reviewers: dict[str, Any] = {}
    removed_count = 0
    for reviewer_id, entry in reviewers.items():
        cleaned_entry, removed_fields = _sanitize_reviewer_entry(entry)
        cleaned_reviewers[str(reviewer_id)] = cleaned_entry
        removed_count += len(removed_fields)
    sanitized["reviewers"] = cleaned_reviewers
    return sanitized, removed_count


def _registry_path(policy_dir: Path) -> Path:
    return policy_dir / "reviewer_key_registry.yaml"


def _load_registry_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": "scope-core-v0.5", "reviewers": {}}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("reviewers", {})
    return data


def _load_registry_file(path: Path) -> dict[str, Any]:
    sanitized, _ = _sanitize_registry_data(_load_registry_raw(path))
    return sanitized


def _save_registry_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)


def list_registry_reviewers(policy_dir: str | Path) -> list[dict[str, Any]]:
    """List reviewer entries from reviewer_key_registry.yaml."""
    registry = _load_registry_file(_registry_path(Path(policy_dir)))
    reviewers = registry.get("reviewers") or {}
    entries: list[dict[str, Any]] = []
    for reviewer_id, entry in sorted(reviewers.items()):
        if isinstance(entry, dict):
            entries.append(
                {
                    "reviewer_id": str(reviewer_id),
                    "public_key_ref": entry.get("public_key_ref"),
                    "public_key_file": entry.get("public_key_file"),
                }
            )
        else:
            entries.append(
                {
                    "reviewer_id": str(reviewer_id),
                    "public_key_ref": str(entry),
                    "public_key_file": None,
                }
            )
    return entries


def verify_registry_integrity(policy_dir: str | Path) -> dict[str, Any]:
    """Verify registry file loads and report version/hash without a decision artifact."""
    policy = PolicyStore.from_dir(policy_dir)
    return {
        "registry_version": policy.reviewer_key_registry_version,
        "registry_hash": policy.reviewer_key_registry_hash,
        "reviewer_count": len(policy.reviewer_key_registry_entries),
        "reviewers": list_registry_reviewers(policy_dir),
    }


def register_reviewer_key(
    policy_dir: str | Path,
    reviewer_id: str,
    public_key_path: str | Path,
) -> dict[str, Any]:
    """Register or update a reviewer public key in the policy registry."""
    policy_path = Path(policy_dir)
    registry = _load_registry_file(_registry_path(policy_path))
    public_ref = Ed25519PublicVerifier(public_key_path).public_key_ref()
    entry: dict[str, Any] = {"public_key_ref": public_ref}
    pub_path = Path(public_key_path)
    try:
        entry["public_key_file"] = str(pub_path.relative_to(policy_path))
    except ValueError:
        entry["public_key_file"] = str(pub_path.resolve())
    reviewers = registry.setdefault("reviewers", {})
    cleaned_entry, _ = _sanitize_reviewer_entry(entry)
    reviewers[str(reviewer_id)] = cleaned_entry
    _save_registry_file(_registry_path(policy_path), registry)
    return {
        "reviewer_id": reviewer_id,
        "public_key_ref": public_ref,
        "registry_version": registry.get("version"),
    }


def verify_decision_against_registry(
    decision: dict[str, Any],
    policy_dir: str | Path,
) -> dict[str, Any]:
    """Verify decision identity binding against reviewer_key_registry.yaml."""
    policy = PolicyStore.from_dir(policy_dir)
    reviewer = decision.get("reviewer") or {}
    reviewer_id = reviewer.get("reviewer_id")
    if not reviewer_id:
        raise ScopeValidationError("Decision missing reviewer.reviewer_id")
    registry_entry = policy.reviewer_key_registry_entries.get(str(reviewer_id))
    if registry_entry is None:
        raise ScopeValidationError(f"No registry entry for reviewer_id {reviewer_id}")
    expected_ref = registry_entry["public_key_ref"]
    declared_ref = reviewer.get("reviewer_public_key_ref") or decision.get(
        "reviewer_public_key_ref"
    )
    if not declared_ref:
        raise ScopeValidationError("Decision missing reviewer_public_key_ref")
    if declared_ref != expected_ref:
        raise ScopeValidationError(
            f"Decision public key ref {declared_ref} does not match registry {expected_ref}"
        )
    signature_valid: bool | None = None
    public_key_file = registry_entry.get("public_key_file")
    if decision.get("decision_signature") and public_key_file:
        key_path = Path(public_key_file)
        if not key_path.is_absolute():
            key_path = Path(policy_dir) / key_path
        if key_path.exists():
            verifier = Ed25519PublicVerifier(key_path, public_key_ref=expected_ref)
            signature_valid = verify_artifact_signature(
                decision,
                verifier,
                hash_field="decision_hash",
                signature_field="decision_signature",
            )
    return {
        "reviewer_id": reviewer_id,
        "public_key_ref": expected_ref,
        "binding_valid": True,
        "signature_valid": signature_valid,
        "registry_version": policy.reviewer_key_registry_version,
        "registry_hash": policy.reviewer_key_registry_hash,
    }


def migrate_reviewer_registry(policy_dir: str | Path) -> dict[str, Any]:
    """Persistently remove legacy private key fields from reviewer_key_registry.yaml."""
    policy_path = Path(policy_dir)
    registry_path = _registry_path(policy_path)
    raw = _load_registry_raw(registry_path)
    sanitized, removed_count = _sanitize_registry_data(raw)
    changed = sanitized != raw
    if changed:
        _save_registry_file(registry_path, sanitized)
    return {
        "registry_path": str(registry_path),
        "removed_private_key_fields": removed_count,
        "changed": changed,
        "reviewer_count": len(sanitized.get("reviewers") or {}),
    }
