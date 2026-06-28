"""SCOPE Decision submission and validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import jsonschema

from scope.config import is_production_mode
from scope.errors import DecisionValidationError, RoleValidationError, ScopeValidationError
from scope.hash import attach_hash
from scope.policy import PolicyStore
from scope.roles import (
    reviewer_info,
    validate_reviewer_for_action,
    validate_reviewer_for_scope,
    validate_single_decision_allowed,
)
from scope.scopes import (
    is_stronger,
    resolve_requested_scope_from_tool,
    scope_rank,
    validate_approval_not_overbroad,
    validate_scope,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_decision_id() -> str:
    return f"SCOPE-DEC-{uuid.uuid4().hex[:6].upper()}"


class DecisionEngine:
    def __init__(self, policy: PolicyStore, schema: dict[str, Any] | None = None) -> None:
        self.policy = policy
        self.schema = schema

    def submit(
        self,
        packet: dict[str, Any],
        reviewer: dict[str, Any],
        decision_input: dict[str, Any],
        *,
        skip_co_review: bool = False,
        session_mode: bool = False,
        allowed_veto_roles: list[str] | None = None,
    ) -> dict[str, Any]:
        action_type = packet["review_request"]["scientific_action_type"]
        domain_overlay = packet.get("scientific_context", {}).get("domain_overlay")
        decision_type = decision_input["type"]
        allowed = self.policy.allowed_decisions(action_type)
        if decision_type not in allowed:
            raise DecisionValidationError(
                f"Decision type '{decision_type}' not allowed for {action_type}"
            )

        if not skip_co_review and not session_mode:
            validate_single_decision_allowed(
                action_type, self.policy, domain_overlay=domain_overlay
            )
            self._reject_legacy_co_reviewers(action_type, decision_input)

        rev = reviewer_info(reviewer, self.policy)
        required_roles = packet["review_request"]["required_review_roles"]
        try:
            validate_reviewer_for_action(
                rev["role"],
                action_type,
                self.policy,
                required_roles=required_roles,
                domain_overlay=domain_overlay,
            )
        except RoleValidationError:
            if not (
                allowed_veto_roles
                and rev["role"] in allowed_veto_roles
                and decision_type == "reject"
            ):
                raise

        decision_body: dict[str, Any] = {
            "type": decision_type,
            "rationale": decision_input.get("rationale", ""),
        }

        if self.policy.is_approval_decision(decision_type):
            approved_scope = decision_input.get("approved_scope")
            if not approved_scope:
                raise DecisionValidationError("Approval decisions require approved_scope")
            validate_scope(approved_scope, self.policy)
            validate_reviewer_for_scope(
                rev["role"], approved_scope, self.policy, session_mode=session_mode
            )

            requested_scope = self._resolve_requested_scope(packet, decision_input)
            requested_tool = packet["review_request"].get("requested_tool")
            self._validate_unknown_scope_approval(
                approved_scope, requested_scope, rev["role"], packet
            )
            validate_approval_not_overbroad(
                approved_scope,
                requested_scope,
                requested_tool,
                self.policy,
            )

            if requested_scope and is_stronger(approved_scope, requested_scope, self.policy):
                raise ScopeValidationError(
                    f"Overbroad approval: '{approved_scope}' exceeds requested "
                    f"'{requested_scope}'"
                )

            decision_body["approved_scope"] = approved_scope
            decision_body["rejected_scope"] = decision_input.get(
                "rejected_scope",
                self._default_rejected_scopes(approved_scope, packet),
            )
            if decision_input.get("required_modifications"):
                decision_body["required_modifications"] = decision_input["required_modifications"]

        decision: dict[str, Any] = {
            "decision_id": _new_decision_id(),
            "packet_id": packet["packet_id"],
            "decided_at": _utc_now(),
            "reviewer": rev,
            "decision": decision_body,
            "confidence": {
                "reviewer_confidence": decision_input.get("reviewer_confidence", 0.5),
                "requires_second_review": decision_input.get("requires_second_review", False),
            },
        }

        if self.policy.is_approval_decision(decision_type):
            scope = decision_body["approved_scope"]
            decision["expiration"] = decision_input.get(
                "expiration",
                {
                    "mode": "event_based",
                    "expires_on": self.policy.get_default_expiration(scope),
                },
            )

        decision = attach_hash(decision, "decision_hash")
        decision["provenance"] = {
            "scope_policy_version": self.policy.version,
            "scope_policy_hash": self.policy.policy_hash,
            "reviewer_key_registry_version": self.policy.reviewer_key_registry_version,
            "reviewer_key_registry_hash": self.policy.reviewer_key_registry_hash,
            "scope_trust_root_hash": self.policy.scope_trust_root_hash,
        }
        sig_fields = (
            "decision_signature",
            "reviewer_public_key_ref",
            "signature_algorithm",
            "signed_payload_hash",
        )
        for field in sig_fields:
            if decision_input.get(field):
                decision[field] = decision_input[field]

        if is_production_mode() and not decision.get("decision_signature"):
            decision["signature_required"] = True

        return decision

    def _resolve_requested_scope(
        self, packet: dict[str, Any], decision_input: dict[str, Any]
    ) -> str | None:
        review_request = packet["review_request"]
        if decision_input.get("manual_requested_scope"):
            scope = str(decision_input["manual_requested_scope"])
            validate_scope(scope, self.policy)
            review_request["requested_scope"] = scope
            review_request["scope_inference_source"] = "manual_override"
            return scope
        explicit = review_request.get("requested_scope")
        if explicit:
            return str(explicit)
        tool = review_request.get("requested_tool")
        inferred = resolve_requested_scope_from_tool(tool, self.policy) if tool else None
        return str(inferred) if inferred else None

    def _validate_unknown_scope_approval(
        self,
        approved_scope: str,
        requested_scope: str | None,
        role: str,
        packet: dict[str, Any],
    ) -> None:
        inference = packet["review_request"].get("scope_inference_source", "unknown")
        if requested_scope or inference != "unknown":
            return
        clarification_rank = scope_rank("clarification_only", self.policy)
        if scope_rank(approved_scope, self.policy) <= clarification_rank:
            return
        if role == "system_owner":
            return
        raise ScopeValidationError(
            "Cannot approve scope stronger than clarification_only when requested scope is unknown"
        )

    def _reject_legacy_co_reviewers(
        self, action_type: str, decision_input: dict[str, Any]
    ) -> None:
        if decision_input.get("co_reviewers"):
            entry = self.policy.role_matrix.get(action_type, {})
            required = entry.get("required_roles", [])
            if entry.get("require_all") and len(required) > 1:
                raise DecisionValidationError(
                    "co_reviewers is not supported for multi-role require_all actions. "
                    "Use 'scope review session' to collect votes from all required roles."
                )

    def _default_rejected_scopes(
        self, approved_scope: str, packet: dict[str, Any]
    ) -> list[str]:
        hierarchy = self.policy.scope_hierarchy
        idx = hierarchy.index(approved_scope)
        stronger = hierarchy[idx + 1 :]
        blocked_tools = packet.get("akta_constraints", {}).get("blocked_tools", [])
        rejected = list(stronger)
        for tool in blocked_tools:
            s = resolve_requested_scope_from_tool(tool, self.policy)
            if s and s not in rejected:
                rejected.append(s)
        return rejected

    def validate(self, decision: dict[str, Any]) -> None:
        if self.schema:
            jsonschema.validate(instance=decision, schema=self.schema)
