"""Canonical SHA256 hashing for SCOPE artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

HASH_FIELDS = frozenset(
    {
        "packet_hash",
        "decision_hash",
        "grant_hash",
        "event_hash",
        "previous_event_hash",
    }
)


def canonical_json(data: Any) -> str:
    """Serialize data to canonical JSON for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def strip_hash_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Remove hash fields before computing artifact hash."""
    return {k: v for k, v in data.items() if k not in HASH_FIELDS}


def compute_hash(data: dict[str, Any], *, field_name: str | None = None) -> str:
    """Compute sha256 hash for an artifact, excluding its own hash field."""
    payload = strip_hash_fields(data)
    if field_name and field_name in payload:
        del payload[field_name]
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def attach_hash(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Return a copy of data with the canonical hash field attached."""
    result = dict(data)
    result[field_name] = compute_hash(result, field_name=field_name)
    return result


def verify_hash(data: dict[str, Any], field_name: str) -> bool:
    """Verify that the hash field matches canonical computation."""
    if field_name not in data:
        return False
    expected = data[field_name]
    actual = compute_hash(data, field_name=field_name)
    return bool(expected == actual)


def combine_sha256_hashes(*hashes: str) -> str:
    """Combine one or more sha256-prefixed digests into a single trust-root hash."""
    parts: list[str] = []
    for value in hashes:
        if not value.startswith("sha256:"):
            raise ValueError(f"Expected sha256-prefixed hash, got: {value!r}")
        parts.append(value)
    digest = hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def scope_trust_root_hash(policy_hash: str, registry_hash: str) -> str:
    """Canonical combined trust root from policy and reviewer key registry hashes."""
    return combine_sha256_hashes(policy_hash, registry_hash)
