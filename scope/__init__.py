"""Scoped Scientific Authorization Protocol (SCOPE) v0.5."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scope._version import __version__
from scope.decisions import DecisionEngine
from scope.grants import GrantEngine
from scope.ledger import ScopeLedger
from scope.packets import PacketBuilder
from scope.policy import PolicyStore
from scope.quality import analyze_ledger, emit_quality_warning, is_weak_evidence
from scope.review_assignment import resolve_review_assignment
from scope.review_queue import ReviewQueue, aggregate_queue_status, queue_metrics
from scope.review_session import ReviewSession
from scope.schema_util import load_schema
from scope.session_store import MemorySessionStore, SessionStore, create_session_store
from scope.signing import (
    Ed25519PublicVerifier,
    Ed25519Signer,
    Signer,
    Verifier,
    attach_signature,
    verify_artifact_signature,
)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_POLICY_DIR = _PACKAGE_ROOT / "policy"


class ScopeEngine:
    """Main SCOPE workflow engine."""

    def __init__(
        self,
        policy: PolicyStore,
        *,
        ledger_path: str | Path | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.policy = policy
        self.ledger = ScopeLedger(ledger_path)
        self._session_store = session_store or MemorySessionStore()
        self._packet_builder = PacketBuilder(
            policy, schema=load_schema("scope_packet.schema.json")
        )
        self._decision_engine = DecisionEngine(
            policy, schema=load_schema("scope_decision.schema.json")
        )
        self._grant_engine = GrantEngine(policy, schema=load_schema("scope_grant.schema.json"))
        self._packet_created_at: dict[str, str] = {}

    @classmethod
    def from_policy_dir(
        cls,
        policy_dir: str | Path | None = None,
        *,
        ledger_path: str | Path | None = None,
        session_store: SessionStore | None = None,
    ) -> ScopeEngine:
        path = Path(policy_dir) if policy_dir else _DEFAULT_POLICY_DIR
        return cls(
            PolicyStore.from_dir(path),
            ledger_path=ledger_path,
            session_store=session_store,
        )

    def create_packet(
        self,
        akta_record: str | Path | dict[str, Any] | None = None,
        akta_trigger: str | Path | dict[str, Any] | None = None,
        *,
        vsa_report: str | Path | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        packet = self._packet_builder.create_from_akta(
            akta_record, akta_trigger, vsa_report=vsa_report
        )
        self._packet_created_at[packet["packet_id"]] = packet["created_at"]
        self.ledger.append(
            "packet_created",
            packet_id=packet["packet_id"],
            metadata={"created_at": packet["created_at"]},
        )
        assignment = resolve_review_assignment(packet, self.policy)
        self.ledger.append(
            "review_assigned",
            packet_id=packet["packet_id"],
            metadata=assignment,
        )
        if packet["review_request"].get("akta_admissibility") == "no_review_needed":
            self.ledger.append(
                "false_review_trigger",
                packet_id=packet["packet_id"],
                metadata={"reason": "Packet created despite no_review_needed admissibility"},
            )
        return packet

    def validate_packet(self, packet: dict[str, Any]) -> None:
        self._packet_builder.validate(packet)

    def open_review(self, packet_id: str, *, actor_id: str | None = None) -> dict[str, Any]:
        return self.ledger.append(
            "review_opened",
            packet_id=packet_id,
            actor_id=actor_id,
        )

    def record_artifact_viewed(
        self,
        packet_id: str,
        artifact_name: str,
        *,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        return self.ledger.append(
            "artifact_viewed",
            packet_id=packet_id,
            actor_id=actor_id,
            metadata={"artifact_name": artifact_name},
        )

    def _decision_ledger_metadata(
        self,
        packet: dict[str, Any],
        reviewer: dict[str, Any],
        decision_input: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = packet.get("scientific_context", {})
        review_request = packet["review_request"]
        meta = {
            "decision_type": result["decision"]["type"],
            "review_duration_seconds": decision_input.get("review_duration_seconds"),
            "scientific_action_type": review_request["scientific_action_type"],
            "reviewer_role": reviewer.get("role"),
            "has_rationale": bool(str(decision_input.get("rationale", "")).strip()),
            "reviewer_confidence": decision_input.get(
                "reviewer_confidence",
                (result.get("confidence") or {}).get("reviewer_confidence"),
            ),
            "evidence_state": ctx.get("evidence_state"),
            "requested_scope": review_request.get("requested_scope"),
            "approved_scope": result["decision"].get("approved_scope"),
            "akta_blocked_tool_count": len(
                packet.get("akta_constraints", {}).get("blocked_tools", [])
            ),
            "scope_inference_source": review_request.get("scope_inference_source"),
        }
        created_at = self._packet_created_at.get(packet["packet_id"]) or packet.get("created_at")
        if created_at and result.get("decided_at"):
            try:
                start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(result["decided_at"].replace("Z", "+00:00"))
                meta["time_to_decision_seconds"] = (end - start).total_seconds()
            except ValueError:
                pass
        return meta

    def _emit_decision_quality_warnings(
        self,
        packet: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        ctx = packet.get("scientific_context", {})
        decision_type = result["decision"]["type"]
        if not self.policy.is_approval_decision(decision_type):
            return

        evidence_state = ctx.get("evidence_state")
        if is_weak_evidence(str(evidence_state) if evidence_state is not None else None):
            warn = emit_quality_warning(
                "approval_despite_low_evidence",
                f"Approval granted with weak evidence state: {evidence_state}.",
            )
            self.ledger.append(
                "quality_warning_emitted",
                packet_id=packet["packet_id"],
                decision_id=result["decision_id"],
                metadata=warn,
            )

        akta_blocked = packet.get("akta_constraints", {}).get("blocked_tools", [])
        approved_scope = result["decision"].get("approved_scope")
        if approved_scope and akta_blocked:
            grant_blocked_preview = set(
                packet.get("akta_constraints", {}).get("blocked_tools", [])
            )
            from scope.scopes import blocked_tools_for_scope

            scope_blocked = set(blocked_tools_for_scope(approved_scope, self.policy))
            merged = scope_blocked | grant_blocked_preview
            missing = [tool for tool in akta_blocked if tool not in merged]
            if missing:
                warn = emit_quality_warning(
                    "residual_block_violation",
                    f"Approval may not preserve AKTA blocked tools: {missing}",
                )
                self.ledger.append(
                    "quality_warning_emitted",
                    packet_id=packet["packet_id"],
                    decision_id=result["decision_id"],
                    metadata=warn,
                )

        requested_scope = packet["review_request"].get("requested_scope")
        approved = result["decision"].get("approved_scope")
        if approved and requested_scope:
            from scope.scopes import is_stronger

            if is_stronger(approved, requested_scope, self.policy):
                warn = emit_quality_warning(
                    "scope_overbreadth",
                    f"Reviewer approved {approved} when packet requested only {requested_scope}.",
                )
                self.ledger.append(
                    "quality_warning_emitted",
                    packet_id=packet["packet_id"],
                    decision_id=result["decision_id"],
                    metadata=warn,
                )

    def submit_decision(
        self,
        packet: dict[str, Any],
        reviewer: str | Path | dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(reviewer, dict):
            with Path(reviewer).open(encoding="utf-8") as fh:
                reviewer_data = json.load(fh)
        else:
            reviewer_data = reviewer

        result = self._decision_engine.submit(packet, reviewer_data, decision)
        self.ledger.append(
            "decision_submitted",
            actor_id=reviewer_data.get("reviewer_id"),
            reviewer_role=reviewer_data.get("role"),
            packet_id=packet["packet_id"],
            decision_id=result["decision_id"],
            metadata=self._decision_ledger_metadata(packet, reviewer_data, decision, result),
        )
        self._emit_decision_quality_warnings(packet, result)
        return result

    def validate_decision(
        self, decision: dict[str, Any], *, require_signature: bool = False
    ) -> None:
        self._decision_engine.validate(decision)
        if require_signature:
            from scope.signing import validate_signature_required

            validate_signature_required(decision, "decision_signature")

    def get_review_session(
        self,
        session_id: str,
        packet: dict[str, Any] | None = None,
    ) -> ReviewSession:
        artifact = self._session_store.load(session_id)
        if packet is None:
            packet = artifact.get("packet_snapshot")
            if not packet or not packet.get("review_request"):
                raise ValueError(
                    f"Session {session_id} requires full packet or stored packet_snapshot"
                )
        elif packet.get("packet_id") != artifact["packet_id"]:
            raise ValueError(
                f"Provided packet_id {packet.get('packet_id')} does not match session "
                f"{artifact['packet_id']}"
            )
        return ReviewSession.from_artifact(artifact, packet, self.policy)

    def session_status(self, session_id: str) -> dict[str, Any]:
        return self._session_store.status(session_id)

    def _persist_session(self, session: ReviewSession) -> None:
        self._session_store.save(session.to_artifact())

    def create_review_session(
        self,
        packet: dict[str, Any],
        *,
        quorum_policy: dict[str, Any] | None = None,
    ) -> ReviewSession:
        session = ReviewSession(packet, self.policy, quorum_policy=quorum_policy)
        self._persist_session(session)
        self.ledger.append(
            "review_session_created",
            packet_id=packet["packet_id"],
            metadata={"session_id": session.session_id},
        )
        return session

    def submit_session_decision(
        self,
        session: ReviewSession,
        packet: dict[str, Any],
        reviewer: dict[str, Any],
        decision: dict[str, Any],
        *,
        replace_vote: bool = False,
    ) -> dict[str, Any]:
        veto_roles = session.quorum_policy.get("safety_veto_roles") or []
        result = self._decision_engine.submit(
            packet,
            reviewer,
            decision,
            skip_co_review=True,
            session_mode=True,
            allowed_veto_roles=veto_roles,
        )
        self.ledger.append(
            "decision_submitted",
            actor_id=reviewer.get("reviewer_id"),
            reviewer_role=reviewer.get("role"),
            packet_id=packet["packet_id"],
            decision_id=result["decision_id"],
            metadata=self._decision_ledger_metadata(packet, reviewer, decision, result),
        )
        session.add_vote(result, replace=replace_vote)
        self._persist_session(session)
        self._emit_decision_quality_warnings(packet, result)
        self.ledger.append(
            "reviewer_vote_recorded",
            actor_id=reviewer.get("reviewer_id"),
            reviewer_role=reviewer.get("role"),
            packet_id=packet["packet_id"],
            decision_id=result["decision_id"],
            metadata={"session_id": session.session_id, "replace_vote": replace_vote},
        )
        return result

    def issue_grant_from_session(
        self,
        session: ReviewSession,
        packet: dict[str, Any],
        decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        resolution = session.resolve()
        first_id = resolution["contributing_decisions"][0]
        primary = next(d for d in decisions if d["decision_id"] == first_id)
        merged = dict(primary)
        merged["decision"]["approved_scope"] = resolution["approved_scope"]
        merged["session_resolution"] = resolution
        contributing_signatures = []
        for decision in decisions:
            if decision["decision_id"] in resolution["contributing_decisions"]:
                entry = {
                    "decision_id": decision["decision_id"],
                    "reviewer_id": decision["reviewer"]["reviewer_id"],
                    "reviewer_role": decision["reviewer"]["role"],
                }
                for field in (
                    "decision_signature",
                    "reviewer_public_key_ref",
                    "signature_algorithm",
                    "signed_payload_hash",
                ):
                    if decision.get(field):
                        entry[field] = decision[field]
                contributing_signatures.append(entry)
        grant = self._grant_engine.issue(
            packet,
            merged,
            contributing_signatures=contributing_signatures,
        )
        akta_blocked = packet.get("akta_constraints", {}).get("blocked_tools", [])
        grant_blocked = grant.get("authorization", {}).get("blocked_tools", [])
        preserved = all(tool in grant_blocked for tool in akta_blocked)
        self.ledger.append(
            "grant_issued",
            packet_id=packet["packet_id"],
            decision_id=merged["decision_id"],
            grant_id=grant["grant_id"],
            metadata={
                "scientific_action_type": packet["review_request"]["scientific_action_type"],
                "residual_blocks_preserved": preserved,
                "session_id": session.session_id,
            },
        )
        return grant

    def issue_grant(
        self,
        packet: dict[str, Any],
        decision: dict[str, Any],
        *,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        grant = self._grant_engine.issue(packet, decision, constraints=constraints)
        akta_blocked = packet.get("akta_constraints", {}).get("blocked_tools", [])
        grant_blocked = grant.get("authorization", {}).get("blocked_tools", [])
        preserved = all(tool in grant_blocked for tool in akta_blocked)
        self.ledger.append(
            "grant_issued",
            packet_id=packet["packet_id"],
            decision_id=decision["decision_id"],
            grant_id=grant["grant_id"],
            metadata={
                "scientific_action_type": packet["review_request"]["scientific_action_type"],
                "residual_blocks_preserved": preserved,
            },
        )
        return grant

    def revoke_grant(
        self,
        grant_id: str,
        *,
        reason: str = "Manual revocation",
        reviewer_withdrawal: bool = False,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {"reason": reason}
        if reviewer_withdrawal:
            metadata["reviewer_withdrawal"] = True
        event = self.ledger.append(
            "grant_revoked",
            grant_id=grant_id,
            metadata=metadata,
        )
        return event

    def grant_status(self, grant_id: str) -> dict[str, Any]:
        return self.ledger.grant_status(grant_id)

    def check_grant(
        self,
        grant: dict[str, Any],
        requested_tool: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        result = self.check_grant_detailed(grant, requested_tool, context)
        return bool(result["allowed"])

    def check_grant_detailed(
        self,
        grant: dict[str, Any],
        requested_tool: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        grant_id = grant["grant_id"]
        ledger_used = self.ledger.grant_used(grant_id)
        ledger_revoked = self.ledger.grant_revoked(grant_id)

        ok, reason, code = self._grant_engine.check(
            grant,
            requested_tool,
            context,
            ledger_used=ledger_used,
            ledger_revoked=ledger_revoked,
        )
        if not ok:
            from scope.expiration import is_expired

            if ledger_revoked:
                pass
            elif ledger_used and grant.get("constraints", {}).get("single_use"):
                self.ledger.append(
                    "grant_expired",
                    grant_id=grant_id,
                    metadata={
                        "reason": "Single-use grant already consumed per ledger",
                        "requested_tool": requested_tool,
                        "post_approval_failure": True,
                    },
                )
            elif is_expired(grant, context, used=ledger_used):
                self.ledger.append(
                    "grant_expired",
                    grant_id=grant_id,
                    metadata={
                        "reason": reason or "Grant expired after context change.",
                        "requested_tool": requested_tool,
                        "scientific_action_type": grant.get("authorization", {}).get(
                            "approved_actions", ["unknown"]
                        )[0],
                        "post_approval_failure": True,
                    },
                )
            else:
                self.ledger.append(
                    "runtime_scope_violation_attempted",
                    grant_id=grant_id,
                    metadata={
                        "reason": reason or f"Tool '{requested_tool}' not allowed by grant.",
                        "requested_tool": requested_tool,
                    },
                )
        else:
            self.ledger.append(
                "grant_used",
                grant_id=grant_id,
                metadata={"requested_tool": requested_tool},
            )
        return {"allowed": ok, "reason": reason, "code": code if not ok else "allowed"}

    def sign_decision(
        self,
        decision: dict[str, Any],
        signer: Signer,
    ) -> dict[str, Any]:
        return attach_signature(
            decision,
            signer,
            hash_field="decision_hash",
            signature_field="decision_signature",
            reviewer_id=(decision.get("reviewer") or {}).get("reviewer_id"),
            key_registry=self.policy.reviewer_key_registry,
        )

    def sign_grant(
        self,
        grant: dict[str, Any],
        signer: Signer,
    ) -> dict[str, Any]:
        return attach_signature(
            grant,
            signer,
            hash_field="grant_hash",
            signature_field="grant_signature",
            key_registry=self.policy.reviewer_key_registry,
        )

    def verify_decision(
        self,
        decision: dict[str, Any],
        verifier: Signer | Verifier,
    ) -> bool:
        return verify_artifact_signature(
            decision, verifier, hash_field="decision_hash", signature_field="decision_signature"
        )

    def verify_grant(
        self,
        grant: dict[str, Any],
        verifier: Signer | Verifier,
    ) -> bool:
        return verify_artifact_signature(
            grant, verifier, hash_field="grant_hash", signature_field="grant_signature"
        )

    def quality_report(self, *, queue_dir: str | Path | None = None) -> dict[str, Any]:
        report = analyze_ledger(self.ledger.events(), self.policy)
        qm = queue_metrics(queue_dir)
        report["metrics"]["open_queue_count"] = qm["open_queue_count"]
        report["metrics"]["overdue_queue_count"] = qm["overdue_queue_count"]
        report["summary"]["open_queue_count"] = qm["open_queue_count"]
        report["summary"]["overdue_queue_count"] = qm["overdue_queue_count"]
        return report

    def create_review_queue(
        self,
        packet: dict[str, Any],
        *,
        queue_dir: str | Path | None = None,
        sla_hours: int = 72,
    ) -> ReviewQueue:
        return ReviewQueue.create(
            packet,
            sla_hours=sla_hours,
            queue_dir=queue_dir,
            persist=queue_dir is not None,
        )

    def assign_review_queue(
        self,
        queue: ReviewQueue | str | Path,
        reviewer: dict[str, Any],
        *,
        queue_path: str | Path | None = None,
    ) -> ReviewQueue:
        if isinstance(queue, ReviewQueue):
            entry = queue
            save_path = queue_path
        else:
            save_path = queue_path or queue
            entry = ReviewQueue.load(save_path)
        entry.assign(reviewer)
        entry.save(save_path)
        return entry

    def decide_review_queue(
        self,
        queue: str | Path,
        decision_id: str,
    ) -> ReviewQueue:
        entry = ReviewQueue.load(queue)
        entry.mark_decided(decision_id)
        entry.save(queue)
        return entry

    def grant_review_queue(
        self,
        queue: str | Path,
        grant_id: str,
    ) -> ReviewQueue:
        entry = ReviewQueue.load(queue)
        entry.mark_granted(grant_id)
        entry.save(queue)
        return entry

    def close_review_queue(
        self,
        queue: str | Path,
        *,
        reason: str = "",
    ) -> ReviewQueue:
        entry = ReviewQueue.load(queue)
        entry.close(reason=reason)
        entry.save(queue)
        return entry

    def review_queue_status(self, *, queue_dir: str | Path | None = None) -> dict[str, Any]:
        return aggregate_queue_status(queue_dir)


__all__ = [
    "ScopeEngine",
    "Ed25519Signer",
    "Ed25519PublicVerifier",
    "create_session_store",
    "SessionStore",
    "__version__",
]
