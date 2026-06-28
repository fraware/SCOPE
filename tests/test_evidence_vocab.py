"""Tests for expanded evidence vocabulary (SCOPE-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scope import ScopeEngine
from scope.quality import WEAK_EVIDENCE_STATES, is_weak_evidence

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "evidence_state",
    [
        "E0_no_evidence",
        "E1_anecdotal_or_informal_observation",
        "E2_preliminary_signal",
    ],
)
def test_weak_evidence_states_emit_warning(tmp_path, evidence_state: str):
    engine = ScopeEngine.from_policy_dir(
        ROOT / "policy", ledger_path=tmp_path / "events.jsonl"
    )
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {"evidence_state": evidence_state},
    }
    record = {
        "record_id": f"AKTA-EV-{evidence_state}",
        "scientific_action_type": "A5_protocol_modification",
    }
    packet = engine.create_packet(record, trigger)
    engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "proceeding despite weak evidence",
        },
    )
    report = engine.quality_report()
    warning_types = {w["warning_type"] for w in report["warnings"]}
    assert "approval_despite_low_evidence" in warning_types


def test_strong_evidence_no_warning(tmp_path):
    engine = ScopeEngine.from_policy_dir(
        ROOT / "policy", ledger_path=tmp_path / "events.jsonl"
    )
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {"evidence_state": "E4_internally_consistent_evidence"},
    }
    record = {"record_id": "AKTA-EV-STRONG", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    engine.submit_decision(
        packet,
        {"reviewer_id": "rev1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "protocol_draft",
            "rationale": "adequate evidence",
        },
    )
    report = engine.quality_report()
    warning_types = {w["warning_type"] for w in report["warnings"]}
    assert "approval_despite_low_evidence" not in warning_types


def test_weak_evidence_set_includes_aliases():
    expected = {
        "",
        "E0_unknown",
        "E0_no_evidence",
        "E1_hypothesis",
        "E1_weak_signal",
        "E1_anecdotal_or_informal_observation",
        "E2_preliminary",
        "E2_preliminary_signal",
    }
    assert expected == set(WEAK_EVIDENCE_STATES)
    assert not is_weak_evidence("E4_internally_consistent_evidence")
