"""SCOPE Grant issuance and enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import jsonschema

from scope.config import require_signatures
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
        contributing_signatures: list[dict[str, Any]] | None = None,
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

        from scope._version import __version__

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
            "grant_version": __version__,
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
                "model_version": ctx.get("model_version"),
                "tool_registry_version": ctx.get("tool_registry_version"),
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
                "reviewer_key_registry_version": self.policy.reviewer_key_registry_version,
                "reviewer_key_registry_hash": self.policy.reviewer_key_registry_hash,
                "scope_trust_root_hash": self.policy.scope_trust_root_hash,
            },
        }
        if contributing_signatures:
            grant["contributing_signatures"] = contributing_signatures
        grant = attach_hash(grant, "grant_hash")
        if require_signatures() and not decision.get("decision_signature"):
            raise GrantValidationError(
                "Production mode requires signed decision before grant issue"
            )
        sig_fields = (
            "grant_signature",
            "reviewer_public_key_ref",
            "signature_algorithm",
            "signed_payload_hash",
        )
        for field in sig_fields:
            if decision.get(field):
                grant[field] = decision[field]
        return grant

    def check(
        self,
        grant: dict[str, Any],
        requested_tool: str,
        context: dict[str, Any] | None = None,
        *,
        ledger_used: bool = False,
        ledger_revoked: bool = False,
    ) -> tuple[bool, str | None, str | None]:
        context = context or {}
        if ledger_revoked:
            return False, "Grant revoked per ledger", "grant_revoked"
        used = ledger_used or context.get("grant_used", False)
        try:
            check_expiration(grant, context, used=used)
        except Exception as exc:
            return False, str(exc), "grant_expired"

        auth = grant.get("authorization", {})
        if requested_tool in auth.get("blocked_tools", []):
            return False, f"Tool '{requested_tool}' is blocked by grant", "tool_blocked"
        allowed = auth.get("allowed_tools", [])
        if requested_tool not in allowed:
            return False, f"Tool '{requested_tool}' not in allowed tools", "tool_not_allowed"
        return True, None, None

    def validate(self, grant: dict[str, Any]) -> None:
        if self.schema:
            jsonschema.validate(instance=grant, schema=self.schema)
