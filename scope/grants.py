"""SCOPE Grant issuance and enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import jsonschema

from scope.errors import GrantValidationError
from scope.expiration import check_expiration
from scope.hash import attach_hash
from scope.policy import PolicyStore
from scope.scopes import allowed_tools_for_scope, blocked_tools_for_scope, validate_scope


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_grant_id() -> str:
    return f"SCOPE-GRANT-{uuid.uuid4().hex[:6].upper()}"


class GrantEngine:
    def __init__(self, policy: PolicyStore, schema: dict[str, Any] | None = None) -> None:
        self.policy = policy
        self.schema = schema

    def issue(
        self,
        packet: dict[str, Any],
        decision: dict[str, Any],
        *,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision_type = decision["decision"]["type"]
        if not self.policy.is_approval_decision(decision_type):
            raise GrantValidationError(
                f"Cannot issue grant for non-approval decision: {decision_type}"
            )

        approved_scope = decision["decision"]["approved_scope"]
        validate_scope(approved_scope, self.policy)

        allowed = allowed_tools_for_scope(approved_scope, self.policy)
        blocked = blocked_tools_for_scope(approved_scope, self.policy)
        akta_blocked = packet.get("akta_constraints", {}).get("blocked_tools", [])
        merged_blocked = sorted(set(blocked) | set(akta_blocked))

        ctx = packet.get("scientific_context", {})
        extra = constraints or {}

        auth: dict[str, Any] = {
            "approved_scope": approved_scope,
            "approved_actions": [packet["review_request"]["scientific_action_type"]],
            "allowed_tools": allowed,
            "blocked_tools": merged_blocked,
        }
        max_resp = packet["review_request"].get("responsibility_level")
        if max_resp:
            auth["max_responsibility_level"] = max_resp

        grant: dict[str, Any] = {
            "grant_id": _new_grant_id(),
            "grant_version": "0.1",
            "created_at": _utc_now(),
            "source": {
                "packet_id": packet["packet_id"],
                "decision_id": decision["decision_id"],
                "akta_record_id": packet["source"]["akta_record_id"],
            },
            "authorization": auth,
            "constraints": {
                "single_use": approved_scope
                in ("single_validation_run_draft", "robot_queue_submission"),
                "project_id": extra.get("project_id", ctx.get("project_id", "default")),
                "protocol_version": extra.get(
                    "protocol_version", ctx.get("protocol_version", "protocol_v1")
                ),
                "domain_overlay": ctx.get("domain_overlay"),
                "evidence_state": ctx.get("evidence_state"),
                "validation_status": ctx.get("validation_status"),
                "requires_recording": True,
                "requires_pf_core_trace": True,
            },
            "expiration": {
                "expires_after": decision.get("expiration", {}).get(
                    "expires_on",
                    self.policy.get_default_expiration(approved_scope),
                ),
                "absolute_expiration": decision.get("expiration", {}).get("absolute_expiration"),
            },
            "provenance": {
                "scope_policy_version": self.policy.version,
                "scope_policy_hash": self.policy.policy_hash,
                "akta_policy_hash": extra.get("akta_policy_hash"),
                "reviewer_role_policy_hash": self.policy.policy_hash,
            },
        }
        grant = attach_hash(grant, "grant_hash")
        self.validate(grant)
        return grant

    def check(
        self,
        grant: dict[str, Any],
        requested_tool: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        context = context or {}
        try:
            check_expiration(grant, context, used=context.get("grant_used", False))
        except Exception:
            return False

        auth = grant.get("authorization", {})
        if requested_tool in auth.get("blocked_tools", []):
            return False
        allowed = auth.get("allowed_tools", [])
        if requested_tool not in allowed:
            return False
        return True

    def validate(self, grant: dict[str, Any]) -> None:
        if self.schema:
            jsonschema.validate(instance=grant, schema=self.schema)
