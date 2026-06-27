"""Scoped Scientific Authorization Protocol (SCOPE) v0.1."""

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

__version__ = "0.1.0"

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
        akta_record: str | Path | dict[str, Any],
        akta_trigger: str | Path | dict[str, Any],
    ) -> dict[str, Any]:
        packet = self._packet_builder.create_from_akta(akta_record, akta_trigger)
        self.ledger.append("packet_created", packet_id=packet["packet_id"])
        return packet

    def validate_packet(self, packet: dict[str, Any]) -> None:
        self._packet_builder.validate(packet)

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
            packet_id=packet["packet_id"],
            decision_id=result["decision_id"],
            metadata={
                "decision_type": result["decision"]["type"],
                "review_duration_seconds": decision.get("review_duration_seconds"),
            },
        )

        # Quality warning for overbroad scope
        requested_tool = packet["review_request"].get("requested_tool")
        if result["decision"].get("approved_scope") and requested_tool:
            from scope.scopes import is_stronger, resolve_requested_scope_from_tool

            inferred = resolve_requested_scope_from_tool(requested_tool, self.policy)
            approved = result["decision"]["approved_scope"]
            if inferred and is_stronger(approved, inferred, self.policy):
                warn = emit_quality_warning(
                    "scope_overbreadth",
                    f"Reviewer approved {approved} when packet requested only {inferred}.",
                )
                self.ledger.append(
                    "quality_warning_emitted",
                    packet_id=packet["packet_id"],
                    decision_id=result["decision_id"],
                    metadata=warn,
                )

        return result

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
        )
        return grant

    def check_grant(
        self,
        grant: dict[str, Any],
        requested_tool: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        ok = self._grant_engine.check(grant, requested_tool, context)
        if not ok:
            from scope.expiration import is_expired

            if is_expired(grant, context):
                self.ledger.append(
                    "grant_expired",
                    grant_id=grant["grant_id"],
                    metadata={
                        "reason": "Grant expired after protocol version change.",
                        "requested_tool": requested_tool,
                    },
                )
            else:
                self.ledger.append(
                    "runtime_scope_violation_attempted",
                    grant_id=grant["grant_id"],
                    metadata={
                        "reason": f"Tool '{requested_tool}' not allowed by grant.",
                        "requested_tool": requested_tool,
                    },
                )
        else:
            self.ledger.append(
                "grant_used",
                grant_id=grant["grant_id"],
                metadata={"requested_tool": requested_tool},
            )
        return ok

    def quality_report(self) -> dict[str, Any]:
        return analyze_ledger(self.ledger.events(), self.policy)


__all__ = ["ScopeEngine", "__version__"]
