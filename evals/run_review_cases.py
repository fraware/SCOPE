"""Evaluation scenario runner for SCOPE v0.8."""

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
from scope.errors import (
    DecisionValidationError,
    LedgerError,
    RoleValidationError,
    ScopeValidationError,
)
from scope.review_workflow import validate_transition
from scope.signing import Ed25519Signer
from tests.jwt_helpers import build_rs256_jwt, generate_rsa_keypair

POLICY = ROOT / "policy"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
EXTENDED_DIR = SCENARIOS_DIR / "extended"
LEDGER_ENV_KEYS = (
    "SCOPE_LEDGER_DELIVERY_MODE",
    "SCOPE_LEDGER_REMOTE_URL",
    "SCOPE_LEDGER_REMOTE_TOKEN",
)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    message: str


def _save_ledger_env() -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in LEDGER_ENV_KEYS}


def _restore_ledger_env(saved: dict[str, str | None]) -> None:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _apply_ledger_env(scenario: dict[str, Any]) -> None:
    if scenario.get("ledger_delivery_mode"):
        os.environ["SCOPE_LEDGER_DELIVERY_MODE"] = str(scenario["ledger_delivery_mode"])
    if scenario.get("ledger_remote_url"):
        os.environ["SCOPE_LEDGER_REMOTE_URL"] = str(scenario["ledger_remote_url"])


def _run_queue_transition_scenario(scenario: dict[str, Any]) -> ScenarioResult:
    name = scenario["name"]
    trans = scenario["expect_queue_transition_error"]
    try:
        validate_transition(trans["from"], trans["to"])
        return ScenarioResult(
            name,
            False,
            f"Expected transition error for {trans['from']} -> {trans['to']}",
        )
    except ScopeValidationError as exc:
        return ScenarioResult(name, True, f"Correctly rejected: {exc}")


def _assert_identity_provenance(
    scenario: dict[str, Any],
    decision: dict[str, Any],
    grant: dict[str, Any] | None = None,
) -> ScenarioResult | None:
    name = scenario["name"]
    expected_ial = scenario.get("expect_identity_assurance_level")
    if expected_ial:
        actual = (decision.get("provenance") or {}).get("identity_assurance_level")
        if actual != expected_ial:
            return ScenarioResult(
                name,
                False,
                f"Decision IAL {actual} != {expected_ial}",
            )
        if grant is not None:
            grant_ial = (grant.get("provenance") or {}).get("identity_assurance_level")
            if grant_ial != expected_ial:
                return ScenarioResult(
                    name,
                    False,
                    f"Grant IAL {grant_ial} != {expected_ial}",
                )
    expected_source = scenario.get("expect_role_resolution_source")
    if expected_source:
        actual = (decision.get("provenance") or {}).get("role_resolution_source")
        if actual != expected_source:
            return ScenarioResult(
                name,
                False,
                f"Decision role_resolution_source {actual} != {expected_source}",
            )
        if grant is not None:
            grant_source = (grant.get("provenance") or {}).get("role_resolution_source")
            if grant_source != expected_source:
                return ScenarioResult(
                    name,
                    False,
                    f"Grant role_resolution_source {grant_source} != {expected_source}",
                )

    expected_identity_source = scenario.get("expect_identity_source")
    if expected_identity_source:
        actual = (decision.get("provenance") or {}).get("identity_source")
        if actual != expected_identity_source:
            return ScenarioResult(
                name,
                False,
                f"Decision identity_source {actual} != {expected_identity_source}",
            )
        if grant is not None:
            grant_source = (grant.get("provenance") or {}).get("identity_source")
            if grant_source != expected_identity_source:
                return ScenarioResult(
                    name,
                    False,
                    f"Grant identity_source {grant_source} != {expected_identity_source}",
                )

    if grant is not None and scenario.get("expect_authority_checks", True):
        decision_checks = (decision.get("provenance") or {}).get("authority_checks")
        grant_checks = (grant.get("provenance") or {}).get("authority_checks")
        if not decision_checks:
            return ScenarioResult(name, False, "Decision missing authority_checks provenance")
        if not grant_checks:
            return ScenarioResult(name, False, "Grant missing authority_checks provenance")
        if grant_checks != decision_checks:
            return ScenarioResult(
                name,
                False,
                "Grant authority_checks != decision authority_checks",
            )

    expected_sal = scenario.get("expect_signing_assurance_level")
    if expected_sal and grant is not None:
        actual_sal = (grant.get("provenance") or {}).get("signing_assurance_level")
        if actual_sal != expected_sal:
            return ScenarioResult(
                name,
                False,
                f"Grant SAL {actual_sal} != {expected_sal}",
            )

    return None


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

    if scenario.get("expect_queue_transition_error"):
        return _run_queue_transition_scenario(scenario)

    saved_ledger_env = _save_ledger_env()
    try:
        defer_ledger = scenario.get("defer_ledger_env_until_grant")
        if not defer_ledger:
            _apply_ledger_env(scenario)
        with tempfile.TemporaryDirectory() as ledger_tmp:
            ledger_path = None
            if scenario.get("ledger_delivery_mode"):
                ledger_path = Path(ledger_tmp) / "events.jsonl"
            engine = ScopeEngine.from_policy_dir(POLICY, ledger_path=ledger_path)
            return _run_scenario_with_engine(engine, scenario, defer_ledger_env=defer_ledger)
    finally:
        _restore_ledger_env(saved_ledger_env)


def _run_akta_review_scenario(
    engine: ScopeEngine,
    scenario: dict[str, Any],
) -> ScenarioResult:
    from scope.akta_review import run_akta_review
    from scope.schema_util import validate_artifact

    name = scenario["name"]
    session_mode = bool(scenario.get("session_mode"))
    session_complete = bool(scenario.get("session_complete"))
    with tempfile.TemporaryDirectory() as out_dir:
        signing_key: Path | None = None
        if scenario.get("sign_before_grant"):
            key = Path(out_dir) / "reviewer.pem"
            pub = Path(out_dir) / "reviewer.pub"
            Ed25519Signer.generate_keypair(key, pub)
            signing_key = key
        summary = run_akta_review(
            engine,
            akta_record=scenario["akta_record"],
            akta_trigger=scenario["akta_trigger"],
            grant_scope=scenario.get("grant_scope", scenario["decision"]["approved_scope"]),
            reviewer=scenario["reviewer"],
            decision_rationale=scenario["decision"]["rationale"],
            out_dir=out_dir,
            signing_key=signing_key,
            session_mode=session_mode,
            session_complete=session_complete,
            votes=scenario.get("votes"),
        )

        if session_mode:
            validate_artifact(summary, "scope_akta_review_session_summary.schema.json")
            if summary.get("status") != "session_required":
                return ScenarioResult(
                    name,
                    False,
                    f"Expected session_required, got {summary.get('status')}",
                )
            if not summary.get("session_id", "").startswith("SCOPE-SESS-"):
                return ScenarioResult(name, False, "Missing session_id")
            packet_path = Path(summary["packet_path"])
            if not packet_path.is_file():
                return ScenarioResult(name, False, "Missing packet_path artifact")
            if Path(out_dir, "scope_grant.json").is_file():
                return ScenarioResult(name, False, "Grant should not be issued in session mode")
            return ScenarioResult(name, True, "AKTA session summary contract OK")

        validate_artifact(summary, "scope_akta_review_summary.schema.json")
        expected_sal = scenario.get("expect_signing_assurance_level")
        if expected_sal and summary.get("signing_assurance_level") != expected_sal:
            return ScenarioResult(
                name,
                False,
                f"Summary SAL {summary.get('signing_assurance_level')} != {expected_sal}",
            )
        expected_ial = scenario.get("expect_identity_assurance_level")
        if expected_ial and summary.get("identity_assurance_level") != expected_ial:
            return ScenarioResult(
                name,
                False,
                f"Summary IAL {summary.get('identity_assurance_level')} != {expected_ial}",
            )
        for field in ("packet_path", "decision_path", "grant_path"):
            path = Path(summary[field])
            if not path.is_file():
                return ScenarioResult(name, False, f"Missing artifact: {field}")
        return ScenarioResult(name, True, "AKTA review contract OK")


def _run_scenario_with_engine(
    engine: ScopeEngine,
    scenario: dict[str, Any],
    *,
    defer_ledger_env: bool = False,
) -> ScenarioResult:
    name = scenario["name"]
    try:
        if scenario.get("run_akta_review"):
            return _run_akta_review_scenario(engine, scenario)

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
            if scenario.get("enforce_rbac"):
                os.environ["SCOPE_ENFORCE_RBAC"] = "true"
            decision = engine.submit_decision(
                packet,
                scenario["reviewer"],
                scenario["decision"],
                identity_token=token,
                enforce_rbac=scenario.get("enforce_rbac"),
            )
            identity_check = _assert_identity_provenance(scenario, decision)
            if identity_check is not None:
                return identity_check
            grant = engine.issue_grant(packet, decision)
            identity_check = _assert_identity_provenance(scenario, decision, grant)
            if identity_check is not None:
                return identity_check
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

        if scenario.get("expect_grant_error"):
            if defer_ledger_env:
                from scope.ledger import ScopeLedger

                _apply_ledger_env(scenario)
                assert engine.ledger.path is not None
                engine.ledger = ScopeLedger(engine.ledger.path)
            try:
                engine.issue_grant(packet, decision)
                return ScenarioResult(name, False, "Expected grant error but succeeded")
            except LedgerError as exc:
                if "grant_issued" not in str(exc) and defer_ledger_env:
                    return ScenarioResult(
                        name,
                        False,
                        f"Expected grant_issued fail_closed error, got: {exc}",
                    )
                return ScenarioResult(name, True, f"Correctly rejected: {exc}")

        grant = engine.issue_grant(packet, decision)
        identity_check = _assert_identity_provenance(scenario, decision, grant)
        if identity_check is not None:
            return identity_check

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
        if scenario.get("expect_grant_error") and isinstance(exc, LedgerError):
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
    "identity_assurance_caller_ial0.json",
    "identity_assurance_local_signed_ial1.json",
    "queue_invalid_transition.json",
    "fail_closed_grant_blocked.json",
    "akta_review_signed_summary.json",
    "akta_review_session_mode.json",
    "akta_review_session_complete.json",
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
        help="Also run extended v0.8 scenarios (IAL, SAL, queue, ledger, AKTA contract)",
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
