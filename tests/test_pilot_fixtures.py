"""Validate examples/pilot fixture pack completeness (SCOPE-4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scope.schema_util import validate_artifact

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
            "summary.json",
            "reviewer_protocol_owner.json",
            "reviewer_domain_scientist.json",
            "decision_protocol_owner.json",
            "decision_domain_scientist.json",
            "packet_rendered.md",
            "quality_report_snippet.json",
            "README.md",
        ],
        "summary_status": "session_required",
        "forbidden_files": ["scope_grant.json"],
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
    snippet_path = PILOT / scenario / "quality_report_snippet.json"
    snippet = json.loads(snippet_path.read_text(encoding="utf-8"))
    assert snippet.get("policy_version") == "scope-core-v0.8"


@pytest.mark.parametrize(
    "scenario",
    [name for name, spec in SCENARIOS.items() if "summary_status" in spec],
)
def test_pilot_summary_contract(scenario: str) -> None:
    spec = SCENARIOS[scenario]
    summary = json.loads((PILOT / scenario / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == spec["summary_status"]
    assert summary["adapter_contract_version"] == "scope-akta-review-v0.8"
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
