"""SCOPE Packet creation and validation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import jsonschema

from scope.errors import SchemaValidationError
from scope.hash import attach_hash
from scope.policy import PolicyStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_packet_id() -> str:
    return f"SCOPE-PKT-{uuid.uuid4().hex[:6].upper()}"


def _load_json(path_or_data: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_data, dict):
        return path_or_data
    path = Path(path_or_data)
    with path.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


class PacketBuilder:
    def __init__(self, policy: PolicyStore, schema: dict[str, Any] | None = None) -> None:
        self.policy = policy
        self.schema = schema

    def create_from_akta(
        self,
        akta_record: str | Path | dict[str, Any],
        akta_trigger: str | Path | dict[str, Any],
    ) -> dict[str, Any]:
        record = _load_json(akta_record)
        trigger = _load_json(akta_trigger)

        action_type = trigger.get("scientific_action_type") or record.get("scientific_action_type")
        if not action_type:
            raise SchemaValidationError("Missing scientific_action_type in AKTA inputs")

        required_roles = self.policy.get_required_roles(action_type)
        admissibility = trigger.get("akta_admissibility") or record.get("decision", {}).get(
            "admissibility", "review_required"
        )

        record_id = record.get("record_id") or trigger.get("akta_record_id") or "AKTA-UNKNOWN"
        decision_id = trigger.get("akta_decision_id") or record.get("decision_id")
        trigger_id = trigger.get("trigger_id") or trigger.get("review_trigger_id")

        source: dict[str, Any] = {"akta_record_id": record_id}
        if decision_id:
            source["akta_decision_id"] = decision_id
        if trigger_id:
            source["review_trigger_id"] = trigger_id

        review_request: dict[str, Any] = {
            "requested_action": trigger.get("requested_action", record.get("requested_action")),
            "requested_tool": trigger.get("requested_tool", record.get("requested_tool")),
            "scientific_action_type": action_type,
            "akta_admissibility": admissibility,
            "required_review_roles": required_roles,
        }
        responsibility = trigger.get("responsibility_level") or record.get("responsibility_level")
        if responsibility:
            review_request["responsibility_level"] = responsibility

        packet: dict[str, Any] = {
            "packet_id": _new_packet_id(),
            "packet_version": "0.1",
            "created_at": _utc_now(),
            "source": source,
            "review_request": review_request,
            "scientific_context": trigger.get(
                "scientific_context",
                record.get(
                    "scientific_context",
                    {
                        "domain": record.get("domain", "unknown"),
                        "deployment_profile": record.get("deployment_profile"),
                        "domain_overlay": record.get("domain_overlay"),
                        "evidence_state": record.get("evidence_state", "E0_unknown"),
                        "validation_status": record.get("validation_status", "V0_unknown"),
                        "verification_status": record.get("verification_status", "Q0_unchecked"),
                    },
                ),
            ),
            "review_artifacts": trigger.get("review_artifacts", record.get("review_artifacts", {})),
            "akta_constraints": trigger.get(
                "akta_constraints",
                record.get(
                    "akta_constraints",
                    {"blocked_tools": [], "allowed_next_steps": []},
                ),
            ),
            "decision_options": self.policy.allowed_decisions(action_type),
        }
        packet = attach_hash(packet, "packet_hash")
        self.validate(packet)
        return packet

    def validate(self, packet: dict[str, Any]) -> None:
        if self.schema:
            jsonschema.validate(instance=packet, schema=self.schema)
