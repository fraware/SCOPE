"""AKTA-integrated review workflow (packet, decision, grant)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scope import ScopeEngine
from scope.config import is_production_mode
from scope.errors import GrantValidationError, ScopeValidationError
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION
from scope.review_assignment import resolve_review_assignment
from scope.schema_util import validate_artifact
from scope.scopes import is_stronger, is_weaker_or_equal, validate_scope
from scope.signing import Ed25519Signer, Signer


def infer_approval_decision_type(
    action_type: str,
    grant_scope: str,
    requested_scope: str | None,
    policy: Any,
) -> str:
    """Pick an allowed approval decision type for the granted scope."""
    allowed = policy.allowed_decisions(action_type)
    if requested_scope and grant_scope == requested_scope:
        if "approve" in allowed:
            return "approve"
    if requested_scope and is_weaker_or_equal(grant_scope, requested_scope, policy):
        if "approve_narrower_scope" in allowed:
            return "approve_narrower_scope"
        if "approve" in allowed:
            return "approve"
    if requested_scope and is_stronger(grant_scope, requested_scope, policy):
        raise ValueError(
            f"Grant scope '{grant_scope}' exceeds requested scope '{requested_scope}'"
        )
    if "approve_narrower_scope" in allowed:
        return "approve_narrower_scope"
    if "approve" in allowed:
        return "approve"
    raise ValueError(f"No approval decision type allowed for action {action_type}")


def build_approval_decision_input(
    packet: dict[str, Any],
    grant_scope: str,
    rationale: str,
    policy: Any,
) -> dict[str, Any]:
    validate_scope(grant_scope, policy)
    action_type = packet["review_request"]["scientific_action_type"]
    requested_scope = packet["review_request"].get("requested_scope")
    decision_type = infer_approval_decision_type(
        action_type, grant_scope, requested_scope, policy
    )
    return {
        "type": decision_type,
        "approved_scope": grant_scope,
        "rationale": rationale,
    }


def _check_multi_role_requirement(engine: ScopeEngine, packet: dict[str, Any]) -> None:
    assignment = resolve_review_assignment(packet, engine.policy)
    required = assignment.get("required_roles") or []
    if len(required) <= 1:
        return
    domain_overlay = packet.get("scientific_context", {}).get("domain_overlay")
    overlay = engine.policy.get_domain_overlay(domain_overlay)
    mandatory = (overlay or {}).get("mandatory_session_roles") or []
    if mandatory or engine.policy.requires_multi_reviewer_session(
        packet["review_request"]["scientific_action_type"],
        domain_overlay=domain_overlay,
    ):
        raise ScopeValidationError(
            f"This action requires a multi-role review session (roles: {required}). "
            "Re-run with --session to create a session, or use "
            "`scope review session create` and vote workflow."
        )


def _resolve_signer(
    engine: ScopeEngine,
    *,
    signing_key: str | Path | None = None,
    signing_provider: str | None = None,
    reviewer_id: str | None = None,
) -> Signer | None:
    if signing_provider:
        from scope.signing_providers import resolve_signing_provider

        provider = resolve_signing_provider(
            signing_provider,
            policy_dir=engine.policy.policy_dir,
            key_path=signing_key,
            reviewer_id=reviewer_id,
        )
        return provider.get_signer(reviewer_id=reviewer_id)
    if signing_key:
        return Ed25519Signer(signing_key)
    return None


def run_akta_review(
    engine: ScopeEngine,
    *,
    akta_record: str | Path | dict[str, Any],
    akta_trigger: str | Path | dict[str, Any],
    grant_scope: str,
    reviewer: str | Path | dict[str, Any],
    decision_rationale: str,
    out_dir: str | Path,
    signing_key: str | Path | None = None,
    signing_provider: str | None = None,
    queue_dir: str | Path | None = None,
    identity_token: str | None = None,
    session_mode: bool = False,
    enforce_rbac: bool | None = None,
) -> dict[str, Any]:
    """Create packet, submit approval decision, issue grant; write artifacts to out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    packet = engine.create_packet(akta_record, akta_trigger)
    if isinstance(reviewer, dict):
        reviewer_data = reviewer
    else:
        with Path(reviewer).open(encoding="utf-8") as fh:
            reviewer_data = json.load(fh)

    _check_multi_role_requirement(engine, packet)

    if session_mode:
        session = engine.create_review_session(packet)
        return {
            "status": "session_required",
            "packet_id": packet["packet_id"],
            "session_id": session.session_id,
            "required_roles": resolve_review_assignment(packet, engine.policy).get(
                "required_roles", []
            ),
            "message": "Multi-role review session created; submit votes before grant issue.",
        }

    if engine.ledger.path:
        engine.open_review(packet["packet_id"], actor_id=reviewer_data.get("reviewer_id"))

    decision_input = build_approval_decision_input(
        packet, grant_scope, decision_rationale, engine.policy
    )
    decision = engine.submit_decision(
        packet,
        reviewer_data,
        decision_input,
        identity_token=identity_token,
        enforce_rbac=enforce_rbac,
    )

    signer = _resolve_signer(
        engine,
        signing_key=signing_key,
        signing_provider=signing_provider,
        reviewer_id=str(reviewer_data.get("reviewer_id", "")),
    )
    if is_production_mode():
        if signer is None:
            raise GrantValidationError(
                "Production mode requires a signed decision before grant issue. "
                "Pass --signing-key or --signing-provider."
            )
        decision = engine.sign_decision(decision, signer)
    elif signer is not None:
        decision = engine.sign_decision(decision, signer)

    grant = engine.issue_grant(
        packet,
        decision,
        signing_provider=signing_provider,
    )

    queue_entry = None
    if queue_dir is not None:
        queue_entry = engine.create_review_queue(packet, queue_dir=queue_dir)
        queue_entry.assign(reviewer_data)
        queue_entry.mark_in_review()
        queue_entry.mark_decided(decision["decision_id"])
        queue_entry.mark_granted(grant["grant_id"])
        queue_entry.save()

    packet_path = out / "scope_review_packet.json"
    decision_path = out / "scope_decision.json"
    grant_path = out / "scope_grant.json"
    summary_path = out / "summary.json"

    for path, data in (
        (packet_path, packet),
        (decision_path, decision),
        (grant_path, grant),
    ):
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")

    auth = grant.get("authorization", {})
    provenance = grant.get("provenance") or {}
    requested_scope = packet["review_request"].get("requested_scope")
    summary: dict[str, Any] = {
        "status": "completed",
        "packet_path": str(packet_path),
        "decision_path": str(decision_path),
        "grant_path": str(grant_path),
        "packet_id": packet["packet_id"],
        "decision_id": decision["decision_id"],
        "grant_id": grant["grant_id"],
        "approved_scope": auth.get("approved_scope", grant_scope),
        "requested_scope": requested_scope,
        "allowed_tools": auth.get("allowed_tools", []),
        "blocked_tools": auth.get("blocked_tools", []),
        "decision_type": decision["decision"]["type"],
        "adapter_contract_version": AKTA_REVIEW_CONTRACT_VERSION,
        "identity_assurance_level": provenance.get("identity_assurance_level", "IAL0"),
        "signing_assurance_level": provenance.get("signing_assurance_level", "SAL0"),
        "production_mode": is_production_mode(),
        "scope_trust_root_hash": provenance.get("scope_trust_root_hash"),
    }
    if queue_entry is not None:
        summary["queue_id"] = queue_entry.queue_id
    validate_artifact(summary, "scope_akta_review_summary.schema.json")
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return summary
