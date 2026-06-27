"""AKTA record and trigger field extraction for SCOPE packet building."""

from __future__ import annotations

from typing import Any

from scope.errors import SchemaValidationError


def _nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def extract_record_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Extract flat field map from flat or nested AKTA record."""
    transition = record.get("requested_transition") or {}
    classification = record.get("classification") or {}
    decision = record.get("decision") or {}
    constraints = record.get("akta_constraints") or {}

    return {
        "record_id": record.get("record_id"),
        "decision_id": record.get("decision_id"),
        "requested_action": _first(
            transition.get("requested_action"), record.get("requested_action")
        ),
        "requested_tool": _first(transition.get("requested_tool"), record.get("requested_tool")),
        "scientific_action_type": _first(
            classification.get("scientific_action_type"), record.get("scientific_action_type")
        ),
        "responsibility_level": _first(
            classification.get("responsibility_level"), record.get("responsibility_level")
        ),
        "akta_admissibility": decision.get("admissibility"),
        "evidence_state": _first(
            classification.get("evidence_state"),
            _nested(record, "scientific_context", "evidence_state"),
            record.get("evidence_state"),
        ),
        "validation_status": _first(
            classification.get("validation_status"),
            _nested(record, "scientific_context", "validation_status"),
            record.get("validation_status"),
        ),
        "verification_status": _first(
            classification.get("verification_status"),
            _nested(record, "scientific_context", "verification_status"),
            record.get("verification_status"),
        ),
        "domain": _first(
            record.get("domain"), _nested(record, "scientific_context", "domain")
        ),
        "deployment_profile": _first(
            record.get("deployment_profile"),
            _nested(record, "scientific_context", "deployment_profile"),
        ),
        "domain_overlay": _first(
            record.get("domain_overlay"),
            _nested(record, "scientific_context", "domain_overlay"),
        ),
        "blocked_tools": _first(
            decision.get("blocked_tools"), constraints.get("blocked_tools"), []
        ),
        "allowed_next_steps": _first(
            decision.get("next_admissible_steps"),
            constraints.get("allowed_next_steps"),
            [],
        ),
        "review_artifacts": record.get("review_artifacts", {}),
        "scientific_context": record.get("scientific_context"),
    }


def extract_trigger_fields(trigger: dict[str, Any]) -> dict[str, Any]:
    """Extract flat field map from AKTA review trigger."""
    return {
        "record_id": trigger.get("akta_record_id"),
        "decision_id": trigger.get("akta_decision_id"),
        "trigger_id": _first(trigger.get("trigger_id"), trigger.get("review_trigger_id")),
        "requested_action": trigger.get("requested_action"),
        "requested_tool": trigger.get("requested_tool"),
        "scientific_action_type": trigger.get("scientific_action_type"),
        "responsibility_level": trigger.get("responsibility_level"),
        "akta_admissibility": trigger.get("akta_admissibility"),
        "requested_scope": _first(trigger.get("requested_scope"), trigger.get("review_scope")),
        "scientific_context": trigger.get("scientific_context"),
        "review_artifacts": trigger.get("review_artifacts"),
        "blocked_tools": _nested(trigger, "akta_constraints", "blocked_tools"),
        "allowed_next_steps": _nested(trigger, "akta_constraints", "allowed_next_steps"),
    }


def merge_akta_inputs(
    record: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge record and trigger fields; trigger overrides record on conflict."""
    rec = extract_record_fields(record or {})
    trig = extract_trigger_fields(trigger or {})

    merged = dict(rec)
    for key, value in trig.items():
        if value is not None and value != "" and value != []:
            merged[key] = value
        elif key in ("blocked_tools", "allowed_next_steps") and value == []:
            merged[key] = value

    if not merged.get("scientific_action_type"):
        raise SchemaValidationError("Missing scientific_action_type in AKTA inputs")

    if not merged.get("requested_tool"):
        raise SchemaValidationError("Missing requested_tool in AKTA inputs")

    if not merged.get("requested_action"):
        raise SchemaValidationError("Missing requested_action in AKTA inputs")

    return merged
