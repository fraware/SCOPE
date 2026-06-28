"""Evaluation scenario runner for SCOPE v0.6."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scope import ScopeEngine
from scope.errors import DecisionValidationError, RoleValidationError, ScopeValidationError
from scope.signing import Ed25519Signer
from tests.jwt_helpers import build_rs256_jwt, generate_rsa_keypair

POLICY = ROOT / "policy"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
EXTENDED_DIR = SCENARIOS_DIR / "extended"


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    message: str


def _load(name: str, *, extended: bool = False) -> dict[str, Any]:
    base = EXTENDED_DIR if extended else SCENARIOS_DIR
    path = base / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _run_session_scenario(
    engine: ScopeEngine, scenario: dict[str, Any], packet: dict[str, Any]
) -> ScenarioResult:
    name = scenario["name"]
    session = engine.create_review_session(packet)
    decisions = []
    for vote in scenario["session_votes"]:
        decision = engine.submit_session_decision(
            session,
            packet,
            vote["reviewer"],
            vote["decision"],
        )
        decisions.append(decision)
    grant = engine.issue_grant_from_session(session, packet, decisions)
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
    return ScenarioResult(name, True, "OK")


def run_scenario(scenario: dict[str, Any]) -> ScenarioResult:
    if scenario.get("production_mode"):
        os.environ["SCOPE_PRODUCTION_MODE"] = "true"
    else:
        os.environ.pop("SCOPE_PRODUCTION_MODE", None)

    engine = ScopeEngine.from_policy_dir(POLICY)
    name = scenario["name"]
    try:
        vsa_path = scenario.get("vsa_report_path")
        vsa_report = ROOT / vsa_path if vsa_path else None
        packet = engine.create_packet(
            scenario["akta_record"],
            scenario["akta_trigger"],
            vsa_report=vsa_report,
        )
        if scenario.get("expected_vsa_report_id"):
            vsa = packet.get("review_artifacts", {}).get("vsa_report", {})
            if vsa.get("report_id") != scenario["expected_vsa_report_id"]:
                return ScenarioResult(
                    name,
                    False,
                    f"VSA report_id {vsa.get('report_id')} != {scenario['expected_vsa_report_id']}",
                )

        expected_roles = scenario.get("expected_required_roles", [])
        if expected_roles:
            actual = packet["review_request"]["required_review_roles"]
            if set(expected_roles) != set(actual):
                return ScenarioResult(name, False, f"Roles mismatch: {actual} != {expected_roles}")

        if scenario.get("auto_assign_queue"):
            with tempfile.TemporaryDirectory() as qdir:
                entry = engine.create_review_queue(packet, queue_dir=qdir, auto_assign=True)
                reviewer = entry.to_artifact().get("reviewer") or {}
                expected_id = scenario.get("expected_assigned_reviewer_id")
                expected_role = scenario.get("expected_assigned_role")
                if expected_id and reviewer.get("reviewer_id") != expected_id:
                    return ScenarioResult(
                        name,
                        False,
                        f"Assigned {reviewer.get('reviewer_id')} != {expected_id}",
                    )
                if expected_role and reviewer.get("role") != expected_role:
                    return ScenarioResult(
                        name,
                        False,
                        f"Role {reviewer.get('role')} != {expected_role}",
                    )
            return ScenarioResult(name, True, "Queue auto-assigned")

        if scenario.get("use_oidc_identity"):
            private_key, public_pem = generate_rsa_keypair()
            pem_path = ROOT / ".scope" / "eval_oidc.pub"
            pem_path.parent.mkdir(parents=True, exist_ok=True)
            pem_path.write_bytes(public_pem)
            os.environ["SCOPE_OIDC_PUBLIC_KEY_PEM"] = str(pem_path)
            os.environ["SCOPE_OIDC_ISSUER"] = "https://idp.eval.test"
            os.environ["SCOPE_OIDC_AUDIENCE"] = "scope-eval"
            import time

            token = build_rs256_jwt(
                private_key,
                {
                    "sub": scenario.get("oidc_sub", "ds1"),
                    "scope_role": scenario.get("oidc_role", "domain_scientist"),
                    "iss": "https://idp.eval.test",
                    "aud": "scope-eval",
                    "exp": int(time.time()) + 3600,
                },
            )
            decision = engine.submit_decision(
                packet,
                scenario["reviewer"],
                scenario["decision"],
                identity_token=token,
            )
            grant = engine.issue_grant(packet, decision)
            approved = grant["authorization"]["approved_scope"]
            if scenario.get("expected_scope") and approved != scenario["expected_scope"]:
                return ScenarioResult(
                    name,
                    False,
                    f"Scope {approved} != {scenario['expected_scope']}",
                )
            return ScenarioResult(name, True, "OIDC identity path OK")

        if scenario.get("use_review_session"):
            return _run_session_scenario(engine, scenario, packet)

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

        if scenario.get("sign_before_grant"):
            with tempfile.TemporaryDirectory() as tmp:
                key = Path(tmp) / "reviewer.pem"
                pub = Path(tmp) / "reviewer.pub"
                Ed25519Signer.generate_keypair(key, pub)
                decision = engine.sign_decision(decision, Ed25519Signer(key))

        grant = engine.issue_grant(packet, decision)

        violation = scenario.get("record_runtime_violation")
        if violation:
            engine.record_runtime_violation(
                grant["grant_id"],
                tool=violation["tool"],
                reason=violation["reason"],
            )
            report = engine.quality_report()
            min_count = scenario.get("expected_violation_metric_min", 1)
            actual = report["metrics"].get("runtime_violation_outcome_count", 0)
            if actual < min_count:
                return ScenarioResult(
                    name,
                    False,
                    f"Violation metric {actual} < {min_count}",
                )

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

EXTENDED_SCENARIOS = [
    "a6_multi_review_session.json",
    "domain_overlay_biosecurity_required.json",
    "vsa_enriched_packet_create.json",
    "production_signing_sequence.json",
    "oidc_identity_mock_path.json",
    "queue_auto_assign.json",
    "runtime_violation_outcome_metric.json",
    "biosecurity_mandatory_session.json",
]


def run_all(*, extended: bool = False) -> list[ScenarioResult]:
    results = []
    for fname in SCENARIOS:
        scenario = _load(fname)
        results.append(run_scenario(scenario))
    if extended:
        for fname in EXTENDED_SCENARIOS:
            scenario = _load(fname, extended=True)
            results.append(run_scenario(scenario))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SCOPE evaluation scenarios")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Also run extended v0.5 scenarios (multi-review, signing, VSA, overlay)",
    )
    args = parser.parse_args()

    results = run_all(extended=args.extended)
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
