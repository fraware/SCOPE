"""Evaluation scenario runner for SCOPE v0.1."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scope import ScopeEngine
from scope.errors import DecisionValidationError, RoleValidationError, ScopeValidationError

POLICY = ROOT / "policy"


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    message: str


def _load(name: str) -> dict[str, Any]:
    path = ROOT / "evals" / "scenarios" / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def run_scenario(scenario: dict[str, Any]) -> ScenarioResult:
    engine = ScopeEngine.from_policy_dir(POLICY)
    name = scenario["name"]
    try:
        packet = engine.create_packet(scenario["akta_record"], scenario["akta_trigger"])
        expected_roles = scenario.get("expected_required_roles", [])
        if expected_roles:
            actual = packet["review_request"]["required_review_roles"]
            if set(expected_roles) != set(actual):
                return ScenarioResult(name, False, f"Roles mismatch: {actual} != {expected_roles}")

        if scenario.get("expect_decision_error"):
            try:
                engine.submit_decision(packet, scenario["reviewer"], scenario["decision"])
                return ScenarioResult(name, False, "Expected decision error but succeeded")
            except (DecisionValidationError, RoleValidationError, ScopeValidationError) as exc:
                return ScenarioResult(name, True, f"Correctly rejected: {exc}")

        decision = engine.submit_decision(packet, scenario["reviewer"], scenario["decision"])
        dt = decision["decision"]["type"]

        if scenario.get("expect_no_grant"):
            if engine.policy.is_approval_decision(dt):
                return ScenarioResult(name, False, "Expected no grant but got approval decision")
            return ScenarioResult(name, True, "Non-approval decision as expected")

        grant = engine.issue_grant(packet, decision)
        approved = grant["authorization"]["approved_scope"]
        if scenario.get("expected_scope") and approved != scenario["expected_scope"]:
            return ScenarioResult(name, False, f"Scope {approved} != {scenario['expected_scope']}")

        for tool in scenario.get("expected_allowed_tools", []):
            if tool not in grant["authorization"]["allowed_tools"]:
                return ScenarioResult(name, False, f"Missing allowed tool: {tool}")

        for tool in scenario.get("expected_blocked_tools", []):
            ctx = scenario.get("grant_check_context", {})
            if engine.check_grant(grant, tool, ctx):
                return ScenarioResult(name, False, f"Tool should be blocked: {tool}")

        for tool in scenario.get("expected_allowed_check", []):
            ctx = scenario.get("grant_check_context", {})
            if not engine.check_grant(grant, tool, ctx):
                return ScenarioResult(name, False, f"Tool should be allowed: {tool}")

        stale_ctx = scenario.get("stale_context")
        if stale_ctx:
            for tool in scenario.get("stale_denied_tools", ["protocol_editor.draft_change"]):
                if engine.check_grant(grant, tool, stale_ctx):
                    return ScenarioResult(name, False, f"Stale grant should block: {tool}")

        return ScenarioResult(name, True, "OK")
    except Exception as exc:
        if scenario.get("expect_decision_error"):
            return ScenarioResult(name, True, f"Correctly rejected: {exc}")
        return ScenarioResult(name, False, str(exc))


SCENARIOS = [
    "protocol_draft_correctly_scoped.json",
    "active_protocol_update_overapproved.json",
    "weak_evidence_validation_review.json",
    "queue_prioritization_wrong_reviewer.json",
    "stale_grant_after_protocol_change.json",
    "reviewer_abstains_insufficient_expertise.json",
    "publication_claim_requires_domain_review.json",
    "robot_submission_scope_violation.json",
]


def run_all() -> list[ScenarioResult]:
    results = []
    for fname in SCENARIOS:
        scenario = _load(fname)
        results.append(run_scenario(scenario))
    return results


def main() -> int:
    results = run_all()
    failed = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name}: {r.message}")
        if not r.passed:
            failed += 1
    print(f"\n{len(results) - failed}/{len(results)} scenarios passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
