"""AKTA evidence state alias normalization to canonical SCOPE vocabulary."""

from __future__ import annotations

from typing import Any

# Aliases documented in docs/evidence_vocab_mapping.md
AKTA_EVIDENCE_ALIASES: dict[str, str] = {
    "no_evidence": "E0_no_evidence",
    "E1_anecdotal": "E1_anecdotal_or_informal_observation",
    "anecdotal_or_informal_observation": "E1_anecdotal_or_informal_observation",
    "E3_replicated": "E3_replicated_or_externally_validated",
    "E5_high_confidence": "E5_high_confidence_evidence",
}

CANONICAL_EVIDENCE_STATES = frozenset(
    {
        "E0_unknown",
        "E0_no_evidence",
        "E1_hypothesis",
        "E1_weak_signal",
        "E1_anecdotal_or_informal_observation",
        "E2_preliminary",
        "E2_preliminary_signal",
        "E3_replicated_or_externally_validated",
        "E4_internally_consistent_evidence",
        "E5_high_confidence_evidence",
    }
)


def normalize_evidence_state(raw: str | None) -> tuple[str, str | None]:
    """Return canonical SCOPE evidence state and original AKTA alias when remapped."""
    if raw is None or raw == "":
        return "E0_unknown", None
    text = str(raw)
    canonical = AKTA_EVIDENCE_ALIASES.get(text, text)
    if canonical in CANONICAL_EVIDENCE_STATES:
        return canonical, text if canonical != text else None
    return text, None


def apply_evidence_normalization(
    scientific_context: dict[str, Any],
) -> dict[str, Any]:
    """Normalize evidence_state in scientific_context; preserve AKTA alias in metadata."""
    result = dict(scientific_context)
    raw = result.get("evidence_state")
    canonical, original = normalize_evidence_state(str(raw) if raw is not None else None)
    result["evidence_state"] = canonical
    if original is not None:
        metadata = dict(result.get("metadata") or {})
        metadata["akta_evidence_state"] = original
        result["metadata"] = metadata
    return result
