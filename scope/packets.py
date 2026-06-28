"""SCOPE Packet creation and validation."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import jsonschema

from adapters.akta.evidence_vocab import apply_evidence_normalization
from adapters.akta.field_extraction import merge_akta_inputs
from scope.config import review_route_promotion_enabled
from scope.errors import SchemaValidationError
from scope.hash import attach_hash
from scope.policy import PolicyStore
from scope.schema_util import load_schema
from scope.scopes import resolve_requested_scope_from_tool, validate_scope

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_packet_id() -> str:
    return f"SCOPE-PKT-{uuid.uuid4().hex[:6].upper()}"


def _load_json(path_or_data: str | Path | dict[str, Any] | None) -> dict[str, Any]:
    if path_or_data is None:
        return {}
    if isinstance(path_or_data, dict):
        return path_or_data
    path = Path(path_or_data)
    with path.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


def _validate_akta_input(data: dict[str, Any], schema_name: str) -> None:
    if not data:
        return
    try:
        jsonschema.validate(instance=data, schema=load_schema(schema_name))
    except jsonschema.ValidationError as exc:
        raise SchemaValidationError(str(exc.message)) from exc


def _resolve_requested_scope(
    merged: dict[str, Any],
    policy: PolicyStore,
) -> tuple[str | None, str | None, str]:
    """Return (requested_scope, review_route, scope_inference_source)."""
    review_route = merged.get("review_route")
    if review_route is not None and review_route != "":
        review_route = str(review_route)

    explicit = merged.get("requested_scope")
    if explicit:
        validate_scope(str(explicit), policy)
        logger.info("Scope inference: explicit requested_scope=%s", explicit)
        return str(explicit), review_route, "akta_trigger"

    if (
        review_route
        and review_route_promotion_enabled()
        and review_route in policy.scope_hierarchy
    ):
        validate_scope(review_route, policy)
        logger.info(
            "Scope inference: promoted review_route=%s to requested_scope", review_route
        )
        return review_route, review_route, "review_route_promoted"

    tool = merged.get("requested_tool")
    inferred = resolve_requested_scope_from_tool(tool, policy) if tool else None
    if inferred:
        logger.info("Scope inference: tool_registry inferred scope=%s from tool=%s", inferred, tool)
        return inferred, review_route, "tool_registry"

    if review_route:
        logger.info("Scope inference: review_route=%s kept as routing label only", review_route)
    return None, review_route, "unknown"


class PacketBuilder:
    def __init__(self, policy: PolicyStore, schema: dict[str, Any] | None = None) -> None:
        self.policy = policy
        self.schema = schema

    def create_from_akta(
        self,
        akta_record: str | Path | dict[str, Any] | None = None,
        akta_trigger: str | Path | dict[str, Any] | None = None,
        *,
        vsa_report: str | Path | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = _load_json(akta_record)
        trigger = _load_json(akta_trigger)

        if not record and not trigger:
            raise SchemaValidationError("At least one of akta_record or akta_trigger is required")

        _validate_akta_input(record, "akta_record_import.schema.json")
        _validate_akta_input(trigger, "akta_review_trigger_import.schema.json")

        merged = merge_akta_inputs(record, trigger)
        action_type = merged["scientific_action_type"]
        domain_overlay = merged.get("domain_overlay")
        required_roles = self.policy.get_required_roles(action_type, domain_overlay=domain_overlay)
        admissibility = merged.get("akta_admissibility") or "review_required"

        record_id = merged.get("record_id") or "AKTA-UNKNOWN"
        decision_id = merged.get("decision_id")
        trigger_id = merged.get("trigger_id")

        source: dict[str, Any] = {"akta_record_id": record_id}
        if decision_id:
            source["akta_decision_id"] = decision_id
        if trigger_id:
            source["review_trigger_id"] = trigger_id

        requested_scope, review_route, scope_inference_source = _resolve_requested_scope(
            merged, self.policy
        )

        review_request: dict[str, Any] = {
            "requested_action": merged["requested_action"],
            "requested_tool": merged["requested_tool"],
            "scientific_action_type": action_type,
            "akta_admissibility": admissibility,
            "required_review_roles": required_roles,
            "scope_inference_source": scope_inference_source,
        }
        if requested_scope:
            review_request["requested_scope"] = requested_scope
        if review_route:
            review_request["review_route"] = review_route
        akta_reason = merged.get("akta_decision_reason")
        if akta_reason:
            review_request["akta_decision_reason"] = akta_reason
        responsibility = merged.get("responsibility_level")
        if responsibility:
            review_request["responsibility_level"] = responsibility

        scientific_context: dict[str, Any]
        if merged.get("scientific_context"):
            scientific_context = dict(merged["scientific_context"])
        else:
            scientific_context = {
                "domain": merged.get("domain", "unknown"),
                "deployment_profile": merged.get("deployment_profile"),
                "domain_overlay": merged.get("domain_overlay"),
                "evidence_state": merged.get("evidence_state", "E0_unknown"),
                "validation_status": merged.get("validation_status", "V0_unknown"),
                "verification_status": merged.get("verification_status", "Q0_unchecked"),
            }
        for field, key in (
            ("evidence_state", "evidence_state"),
            ("validation_status", "validation_status"),
            ("verification_status", "verification_status"),
        ):
            unknown_defaults = (None, "E0_unknown", "V0_unknown", "Q0_unchecked")
            if merged.get(key) and scientific_context.get(field) in unknown_defaults:
                scientific_context[field] = merged[key]

        scientific_context = apply_evidence_normalization(scientific_context)

        akta_constraints = {
            "blocked_tools": merged.get("blocked_tools") or [],
            "allowed_next_steps": merged.get("allowed_next_steps") or [],
        }

        review_artifacts = dict(merged.get("review_artifacts") or {})
        if vsa_report is not None:
            from adapters.vsa.import_report import import_vsa_report

            review_artifacts["vsa_report"] = import_vsa_report(vsa_report)

        from scope._version import __version__

        packet: dict[str, Any] = {
            "packet_id": _new_packet_id(),
            "packet_version": __version__,
            "created_at": _utc_now(),
            "source": source,
            "review_request": review_request,
            "scientific_context": scientific_context,
            "review_artifacts": review_artifacts,
            "akta_constraints": akta_constraints,
            "decision_options": self.policy.allowed_decisions(action_type),
        }
        packet = attach_hash(packet, "packet_hash")
        self.validate(packet)
        return packet

    def validate(self, packet: dict[str, Any]) -> None:
        if self.schema:
            jsonschema.validate(instance=packet, schema=self.schema)
