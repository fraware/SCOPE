"""Validate examples/pilot fixture pack completeness (SCOPE-4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scope.schema_util import validate_artifact
from scope.integration_versions import AKTA_REVIEW_CONTRACT_VERSION

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "examples" / "pilot"

SCENARIOS = {
    "single_reviewer_protocol_draft": {
        "required_files": [
            "scope_review_packet.json",
            "scope_decision.json",
            "scope_grant.json",
            "summary.json",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
        "summary_status": "completed",
    },
    "multi_role_genomics_review": {
        "required_files": [
            "scope_review_packet.json",
            "scope_decision.json",
            "scope_grant.json",
            "summary.json",
            "votes.json",
            "reviewer_protocol_owner.json",
            "reviewer_domain_scientist.json",
            "decision_protocol_owner.json",
            "decision_domain_scientist.json",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
        "summary_status": "completed",
        "policy_version": "scope-core-v1.0",
    },
    "expired_queue_reopen": {
        "required_files": [
            "scope_review_packet.json",
            "review_queue_expired.json",
            "review_queue_reopened.json",
            "scope_events.jsonl",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
    },
    "needs_information_flow": {
        "required_files": [
            "scope_review_packet.json",
            "review_queue_needs_information.json",
            "review_queue_in_review.json",
            "reviewer_protocol_owner.json",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
    },
    "registry_signed_decision": {
        "required_files": [
            "scope_review_packet.json",
            "scope_decision.json",
            "scope_grant.json",
            "summary.json",
            "reviewer_protocol_owner.json",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
        "summary_status": "completed",
    },
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_pilot_fixture_files_present(scenario: str) -> None:
    spec = SCENARIOS[scenario]
    base = PILOT / scenario
    for name in spec["required_files"]:
        assert (base / name).is_file(), f"{scenario}: missing {name}"
    for name in spec.get("forbidden_files", []):
        assert not (base / name).exists(), f"{scenario}: unexpected {name}"


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_pilot_quality_snippet_policy_version(scenario: str) -> None:
    spec = SCENARIOS[scenario]
    snippet_path = PILOT / scenario / "quality_report_snippet.json"
    snippet = json.loads(snippet_path.read_text(encoding="utf-8"))
    expected = spec.get("policy_version", "scope-core-v0.8")
    assert snippet.get("policy_version") == expected


@pytest.mark.parametrize(
    "scenario",
    [name for name, spec in SCENARIOS.items() if "summary_status" in spec],
)
def test_pilot_summary_contract(scenario: str) -> None:
    spec = SCENARIOS[scenario]
    summary = json.loads((PILOT / scenario / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == spec["summary_status"]
    assert summary["adapter_contract_version"] == AKTA_REVIEW_CONTRACT_VERSION
    schema = (
        "scope_akta_review_session_summary.schema.json"
        if spec["summary_status"] == "session_required"
        else "scope_akta_review_summary.schema.json"
    )
    validate_artifact(summary, schema)


def test_pilot_index_readme() -> None:
    readme = (PILOT / "README.md").read_text(encoding="utf-8")
    for scenario in SCENARIOS:
        assert scenario in readme


def test_verify_pilot_fixtures_script() -> None:
    """CI verifier script must pass on the committed fixture pack."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_pilot_fixtures.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "All 5 pilot fixture(s) verified." in result.stdout


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_pilot_manifest_and_verification_files(scenario: str) -> None:
    base = PILOT / scenario
    assert (base / "manifest.json").is_file(), f"{scenario}: missing manifest.json"
    assert (base / "expected_verification.json").is_file(), (
        f"{scenario}: missing expected_verification.json"
    )
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["scenario"] == scenario
