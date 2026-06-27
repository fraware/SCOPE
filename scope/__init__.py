"""Scoped Scientific Authorization Protocol (SCOPE) v0.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scope.decisions import DecisionEngine
from scope.grants import GrantEngine
from scope.ledger import ScopeLedger
from scope.packets import PacketBuilder
from scope.policy import PolicyStore
from scope.quality import analyze_ledger, emit_quality_warning
from scope.review_session import ReviewSession
from scope.signing import Ed25519Signer, Signer, attach_signature, verify_artifact_signature

__version__ = "0.2.0"

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_POLICY_DIR = _PACKAGE_ROOT / "policy"
_SCHEMAS_DIR = _PACKAGE_ROOT / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMAS_DIR / name
    with path.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


class ScopeEngine:
    """Main SCOPE workflow engine."""

    def __init__(
        self,
        policy: PolicyStore,
        *,
        ledger_path: str | Path | None = None,
    ) -> None:
        self.policy = policy
        self.ledger = ScopeLedger(ledger_path)
        self._packet_builder = PacketBuilder(
            policy, schema=_load_schema("scope_packet.schema.json")
        )
        self._decision_engine = DecisionEngine(
            policy, schema=_load_schema("scope_decision.schema.json")
        )
        self._grant_engine = GrantEngine(policy, schema=_load_schema("scope_grant.schema.json"))
        self._sessions: dict[str, ReviewSession] = {}

    @classmethod
    def from_policy_dir(
        cls,
        policy_dir: str | Path | None = None,
        *,
        ledger_path: str | Path | None = None,
    ) -> ScopeEngine:
        path = Path(policy_dir) if policy_dir else _DEFAULT_POLICY_DIR
        return cls(PolicyStore.from_dir(path), ledger_path=ledger_path)

    def create_packet(
        self,
        akta_record: str | Path | dict[str, Any] | None = None,
        akta_trigger: str | Path | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        packet = self._packet_builder.create_from_akta(akta_record, akta_trigger)
        self.ledger.append("packet_created", packet_id=packet["packet_id"])
        return packet

    def validate_packet(self, packet: dict[str, Any]) -> None:
        self._packet_builder.validate(packet)

    def _decision_ledger_metadata(
        self,
        packet: dict[str, Any],
        reviewer: dict[str, Any],
        decision_input: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "decision_type": result["decision"]["type"],
            "review_duration_seconds": decision_input.get("review_duration_seconds"),
            "scientific_action_type": packet["review_request"]["scientific_action_type"],
            "reviewer_role": reviewer.get("role"),
            "has_rationale": bool(str(decision_input.get("rationale", "")).strip()),
            "reviewer_confidence": decision_input.get(
                "reviewer_confidence",
                (result.get("confidence") or {}).get("reviewer_confidence"),
            ),
        }

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

        return result

    def get_review_session(self, session_id: str) -> ReviewSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown review session: {session_id}")
        return session

    def create_review_session(
        self,
        packet: dict[str, Any],
        *,
        quorum_policy: dict[str, Any] | None = None,
    ) -> ReviewSession:
        session = ReviewSession(packet, self.policy, quorum_policy=quorum_policy)
        self._sessions[session.session_id] = session
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
    ) -> dict[str, Any]:
        veto_roles = session.quorum_policy.get("safety_veto_roles") or []
        result = self._decision_engine.submit(
            packet,
            reviewer,
            decision,
            skip_co_review=True,
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
        session.add_vote(result)
        self.ledger.append(
            "reviewer_vote_recorded",
            actor_id=reviewer.get("reviewer_id"),
            reviewer_role=reviewer.get("role"),
            packet_id=packet["packet_id"],
            decision_id=result["decision_id"],
            metadata={"session_id": session.session_id},
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
        return self.issue_grant(packet, merged)

    def issue_grant(
        self,
        packet: dict[str, Any],
        decision: dict[str, Any],
        *,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        grant = self._grant_engine.issue(packet, decision, constraints=constraints)
        self.ledger.append(
            "grant_issued",
            packet_id=packet["packet_id"],
            decision_id=decision["decision_id"],
            grant_id=grant["grant_id"],
            metadata={
                "scientific_action_type": packet["review_request"]["scientific_action_type"],
            },
        )
        return grant

    def revoke_grant(self, grant_id: str, *, reason: str = "Manual revocation") -> dict[str, Any]:
        event = self.ledger.append(
            "grant_revoked",
            grant_id=grant_id,
            metadata={"reason": reason},
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
        grant_id = grant["grant_id"]
        ledger_used = self.ledger.grant_used(grant_id)
        ledger_revoked = self.ledger.grant_revoked(grant_id)

        ok, reason = self._grant_engine.check(
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
        return ok

    def sign_decision(
        self,
        decision: dict[str, Any],
        signer: Signer,
    ) -> dict[str, Any]:
        return attach_signature(
            decision, signer, hash_field="decision_hash", signature_field="decision_signature"
        )

    def sign_grant(
        self,
        grant: dict[str, Any],
        signer: Signer,
    ) -> dict[str, Any]:
        return attach_signature(
            grant, signer, hash_field="grant_hash", signature_field="grant_signature"
        )

    def verify_decision(
        self,
        decision: dict[str, Any],
        signer: Signer,
    ) -> bool:
        return verify_artifact_signature(
            decision, signer, hash_field="decision_hash", signature_field="decision_signature"
        )

    def verify_grant(
        self,
        grant: dict[str, Any],
        signer: Signer,
    ) -> bool:
        return verify_artifact_signature(
            grant, signer, hash_field="grant_hash", signature_field="grant_signature"
        )

    def quality_report(self) -> dict[str, Any]:
        return analyze_ledger(self.ledger.events(), self.policy)


__all__ = [
    "ScopeEngine",
    "Ed25519Signer",
    "__version__",
]
