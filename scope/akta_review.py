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
            "Re-run with --session to create a session, --session-complete with "
            "--votes to orchestrate votes and grant issue, or use "
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


def resolve_reviewer_id(
    reviewer_data: dict[str, Any],
    reviewer_id: str | None,
) -> str:
    """Resolve and validate reviewer identity for all AKTA review entry points."""
    artifact_id = reviewer_data.get("reviewer_id")
    if reviewer_id is not None:
        if not artifact_id:
            raise ScopeValidationError("Reviewer artifact missing reviewer_id")
        if str(reviewer_id) != str(artifact_id):
            raise ScopeValidationError(
                f"reviewer_id {reviewer_id!r} does not match reviewer artifact "
                f"reviewer_id {artifact_id!r}"
            )
        return str(reviewer_id)
    if not artifact_id:
        raise ScopeValidationError("Reviewer artifact missing reviewer_id")
    return str(artifact_id)


def validate_summary_artifact(summary: dict[str, Any]) -> None:
    """Validate summary against the schema for its status branch."""
    status = summary.get("status")
    if status == "completed":
        validate_artifact(summary, "scope_akta_review_summary.schema.json")
    elif status == "session_required":
        validate_artifact(summary, "scope_akta_review_session_summary.schema.json")
    else:
        raise ScopeValidationError(
            f"summary.status must be 'completed' or 'session_required', got {status!r}"
        )


def _load_json_ref(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    with Path(value).open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_votes_manifest(votes: str | Path | list[Any] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(votes, (str, Path)):
        with Path(votes).open(encoding="utf-8") as fh:
            raw = json.load(fh)
    else:
        raw = votes
    if isinstance(raw, list):
        entries = raw
    elif isinstance(raw, dict):
        entries = raw.get("votes") or raw.get("session_votes") or []
    else:
        raise ScopeValidationError("votes manifest must be a list or object with votes[]")
    if not entries:
        raise ScopeValidationError("votes manifest must contain at least one vote")
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ScopeValidationError("each vote entry must be an object")
        reviewer = entry.get("reviewer")
        decision = entry.get("decision")
        if reviewer is None or decision is None:
            raise ScopeValidationError("each vote requires reviewer and decision")
        normalized.append(
            {
                "reviewer": _load_json_ref(reviewer),
                "decision": _load_json_ref(decision),
            }
        )
    return normalized


def _write_session_summary(
    out: Path,
    *,
    packet: dict[str, Any],
    session_id: str,
    required_roles: list[str],
    packet_path: Path,
) -> dict[str, Any]:
    requested_scope = packet["review_request"].get("requested_scope")
    summary: dict[str, Any] = {
        "status": "session_required",
        "packet_id": packet["packet_id"],
        "session_id": session_id,
        "required_roles": required_roles,
        "message": "Multi-role review session created; submit votes before grant issue.",
        "requested_scope": requested_scope,
        "packet_path": str(packet_path).replace("\\", "/"),
        "adapter_contract_version": AKTA_REVIEW_CONTRACT_VERSION,
        "production_mode": is_production_mode(),
    }
    validate_summary_artifact(summary)
    with (out / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return summary


def _write_completed_summary(
    out: Path,
    *,
    packet: dict[str, Any],
    packet_path: Path,
    decision_path: Path,
    grant_path: Path,
    decision: dict[str, Any],
    grant: dict[str, Any],
    grant_scope: str,
    queue_entry: Any | None = None,
) -> dict[str, Any]:
    auth = grant.get("authorization", {})
    provenance = grant.get("provenance") or {}
    requested_scope = packet["review_request"].get("requested_scope")
    summary: dict[str, Any] = {
        "status": "completed",
        "packet_path": str(packet_path).replace("\\", "/"),
        "decision_path": str(decision_path).replace("\\", "/"),
        "grant_path": str(grant_path).replace("\\", "/"),
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
    validate_summary_artifact(summary)
    with (out / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return summary


def _run_session_complete(
    engine: ScopeEngine,
    *,
    packet: dict[str, Any],
    votes: list[dict[str, Any]],
    grant_scope: str,
    out: Path,
    signing_key: str | Path | None = None,
    signing_provider: str | None = None,
    queue_dir: str | Path | None = None,
    identity_token: str | None = None,
    enforce_rbac: bool | None = None,
) -> dict[str, Any]:
    session = engine.create_review_session(packet)
    if engine.ledger.path:
        engine.open_review(packet["packet_id"], actor_id=votes[0]["reviewer"].get("reviewer_id"))

    decisions: list[dict[str, Any]] = []
    for vote in votes:
        reviewer_data = vote["reviewer"]
        decision_input = vote["decision"]
        resolved_id = resolve_reviewer_id(reviewer_data, None)
        signer = _resolve_signer(
            engine,
            signing_key=signing_key,
            signing_provider=signing_provider,
            reviewer_id=resolved_id,
        )
        result = engine.submit_session_decision(
            session,
            packet,
            reviewer_data,
            decision_input,
            identity_token=identity_token,
            enforce_rbac=enforce_rbac,
        )
        if is_production_mode() or signer is not None:
            if is_production_mode() and signer is None:
                raise GrantValidationError(
                    "Production mode requires signed session votes before grant issue."
                )
            assert signer is not None
            result = engine.sign_decision(result, signer)
        decisions.append(result)

    grant = engine.issue_grant_from_session(session, packet, decisions)

    queue_entry = None
    if queue_dir is not None:
        queue_entry = engine.create_review_queue(packet, queue_dir=queue_dir)
        queue_entry.assign(votes[0]["reviewer"])
        queue_entry.mark_in_review()
        queue_entry.mark_decided(decisions[0]["decision_id"])
        queue_entry.mark_granted(grant["grant_id"])
        queue_entry.save()

    packet_path = out / "scope_review_packet.json"
    decision_path = out / "scope_decision.json"
    grant_path = out / "scope_grant.json"

    for path, data in ((packet_path, packet), (decision_path, decisions[0]), (grant_path, grant)):
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")

    return _write_completed_summary(
        out,
        packet=packet,
        packet_path=packet_path,
        decision_path=decision_path,
        grant_path=grant_path,
        decision=decisions[0],
        grant=grant,
        grant_scope=grant_scope,
        queue_entry=queue_entry,
    )


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
    reviewer_id: str | None = None,
    queue_dir: str | Path | None = None,
    identity_token: str | None = None,
    session_mode: bool = False,
    session_complete: bool = False,
    votes: str | Path | list[Any] | dict[str, Any] | None = None,
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

    resolved_reviewer_id = resolve_reviewer_id(reviewer_data, reviewer_id)

    if session_complete:
        if votes is None:
            raise ScopeValidationError("--session-complete requires a votes manifest via --votes")
        return _run_session_complete(
            engine,
            packet=packet,
            votes=_load_votes_manifest(votes),
            grant_scope=grant_scope,
            out=out,
            signing_key=signing_key,
            signing_provider=signing_provider,
            queue_dir=queue_dir,
            identity_token=identity_token,
            enforce_rbac=enforce_rbac,
        )

    if session_mode:
        session = engine.create_review_session(packet)
        required_roles = resolve_review_assignment(packet, engine.policy).get("required_roles", [])
        packet_path = out / "scope_review_packet.json"
        with packet_path.open("w", encoding="utf-8") as fh:
            json.dump(packet, fh, indent=2, sort_keys=True)
            fh.write("\n")
        return _write_session_summary(
            out,
            packet=packet,
            session_id=session.session_id,
            required_roles=required_roles,
            packet_path=packet_path,
        )

    _check_multi_role_requirement(engine, packet)

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
        reviewer_id=resolved_reviewer_id,
    )
    if is_production_mode():
        if signer is None:
            raise GrantValidationError(
                "Production mode requires a signed decision before grant issue."
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

    for path, data in ((packet_path, packet), (decision_path, decision), (grant_path, grant)):
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")

    return _write_completed_summary(
        out,
        packet=packet,
        packet_path=packet_path,
        decision_path=decision_path,
        grant_path=grant_path,
        decision=decision,
        grant=grant,
        grant_scope=grant_scope,
        queue_entry=queue_entry,
    )
