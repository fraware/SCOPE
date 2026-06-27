"""Multi-reviewer session and quorum resolution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from scope.errors import DecisionValidationError, GrantValidationError
from scope.policy import PolicyStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_session_id() -> str:
    return f"SCOPE-SESS-{uuid.uuid4().hex[:6].upper()}"


def _new_vote_id() -> str:
    return f"SCOPE-VOTE-{uuid.uuid4().hex[:6].upper()}"


class ReviewSession:
    """Collect reviewer votes and resolve quorum for multi-review actions."""

    def __init__(
        self,
        packet: dict[str, Any],
        policy: PolicyStore,
        *,
        quorum_policy: dict[str, Any] | None = None,
    ) -> None:
        self.packet = packet
        self.policy = policy
        self.action_type = packet["review_request"]["scientific_action_type"]
        self.required_roles = packet["review_request"]["required_review_roles"]
        self.quorum_policy = quorum_policy or self._default_quorum()
        self.session_id = _new_session_id()
        self.votes: list[dict[str, Any]] = []
        self.created_at = _utc_now()

    def _default_quorum(self) -> dict[str, Any]:
        entry = self.policy.role_matrix.get(self.action_type, {})
        if entry.get("require_all"):
            return {"mode": "require_all", "required_roles": self.required_roles}
        if entry.get("require_any"):
            return {"mode": "require_any", "required_roles": self.required_roles}
        roles = self.required_roles[:1] or self.required_roles
        return {"mode": "require_all", "required_roles": roles}

    def add_vote(self, decision: dict[str, Any]) -> dict[str, Any]:
        vote = {
            "vote_id": _new_vote_id(),
            "session_id": self.session_id,
            "decision_id": decision["decision_id"],
            "reviewer_id": decision["reviewer"]["reviewer_id"],
            "reviewer_role": decision["reviewer"]["role"],
            "decision_type": decision["decision"]["type"],
            "approved_scope": decision["decision"].get("approved_scope"),
            "submitted_at": decision["decided_at"],
        }
        self.votes.append(vote)
        return vote

    @classmethod
    def from_artifact(
        cls,
        artifact: dict[str, Any],
        packet: dict[str, Any],
        policy: PolicyStore,
    ) -> ReviewSession:
        """Restore a session from a persisted artifact."""
        session = cls.__new__(cls)
        session.packet = packet
        session.policy = policy
        session.action_type = artifact["scientific_action_type"]
        session.required_roles = artifact["required_roles"]
        session.quorum_policy = artifact["quorum_policy"]
        session.session_id = artifact["session_id"]
        session.votes = list(artifact.get("votes", []))
        session.created_at = artifact["created_at"]
        return session

    def to_artifact(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_version": "0.2",
            "packet_id": self.packet["packet_id"],
            "scientific_action_type": self.action_type,
            "quorum_policy": self.quorum_policy,
            "required_roles": self.required_roles,
            "votes": self.votes,
            "created_at": self.created_at,
            "status": self.status(),
        }

    def status(self) -> str:
        if self._safety_veto():
            return "safety_veto"
        if self._has_conflict():
            return "conflict"
        try:
            self.resolve()
            return "quorum_met"
        except (DecisionValidationError, GrantValidationError):
            if any(v["decision_type"].startswith("reject") for v in self.votes):
                return "rejected"
            return "pending"

    def _has_conflict(self) -> bool:
        approvals = [
            v.get("approved_scope")
            for v in self.votes
            if v["decision_type"] in ("approve", "approve_narrower_scope")
            and v.get("approved_scope")
        ]
        return len(set(approvals)) > 1

    def _safety_veto(self) -> bool:
        if not self.quorum_policy.get("safety_veto_roles"):
            return False
        veto_roles = set(self.quorum_policy["safety_veto_roles"])
        for vote in self.votes:
            if vote["reviewer_role"] in veto_roles and vote["decision_type"] == "reject":
                return True
        return False

    def resolve(self) -> dict[str, Any]:
        """Resolve quorum and return grant-eligible decision summary."""
        if self._safety_veto():
            raise GrantValidationError("Safety veto blocked grant issuance")

        if self._has_conflict():
            raise GrantValidationError("Conflicting approved scopes across reviewers")

        mode = self.quorum_policy.get("mode", "require_all")
        approval_votes = [
            v
            for v in self.votes
            if v["decision_type"] in ("approve", "approve_narrower_scope")
        ]

        if mode == "require_all":
            voted_roles = {v["reviewer_role"] for v in approval_votes}
            missing = [r for r in self.required_roles if r not in voted_roles]
            if missing:
                raise GrantValidationError(f"Quorum not met: missing roles {missing}")
        elif mode == "require_any":
            if not approval_votes:
                raise GrantValidationError("Quorum not met: no approving vote")
        elif mode == "n_of_m":
            n = int(self.quorum_policy.get("n", 1))
            if len(approval_votes) < n:
                raise GrantValidationError(
                    f"Quorum not met: need {n} approvals, got {len(approval_votes)}"
                )
        elif mode == "statistical_co_review":
            ds_votes = [v for v in approval_votes if v["reviewer_role"] == "statistical_reviewer"]
            if not ds_votes:
                raise GrantValidationError("Statistical co-review required but missing")
            if not approval_votes:
                raise GrantValidationError("Quorum not met: no approving vote")
        else:
            raise DecisionValidationError(f"Unknown quorum mode: {mode}")

        if not approval_votes:
            raise GrantValidationError("No approving decisions for grant issuance")

        # Use narrowest approved scope among votes
        scopes = [v["approved_scope"] for v in approval_votes if v.get("approved_scope")]
        if not scopes:
            raise GrantValidationError("Approving votes missing approved_scope")

        narrowest = min(scopes, key=lambda s: self.policy.scope_hierarchy.index(s))
        decision_ids = [v["decision_id"] for v in approval_votes]

        return {
            "approved_scope": narrowest,
            "contributing_decisions": decision_ids,
            "contributing_roles": sorted({v["reviewer_role"] for v in approval_votes}),
            "quorum_mode": mode,
        }
