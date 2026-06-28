"""Tests for AKTA evidence alias normalization at adapter boundary."""

from __future__ import annotations

from pathlib import Path

from adapters.akta.evidence_vocab import normalize_evidence_state
from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent


def test_normalize_akta_aliases():
    canonical, original = normalize_evidence_state("no_evidence")
    assert canonical == "E0_no_evidence"
    assert original == "no_evidence"

    canonical, original = normalize_evidence_state("E3_replicated")
    assert canonical == "E3_replicated_or_externally_validated"
    assert original == "E3_replicated"

    canonical, original = normalize_evidence_state("E4_internally_consistent_evidence")
    assert canonical == "E4_internally_consistent_evidence"
    assert original is None


def test_packet_stores_canonical_evidence_with_akta_metadata(tmp_path):
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {"evidence_state": "no_evidence"},
    }
    record = {"record_id": "AKTA-EV-NORM", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    ctx = packet["scientific_context"]
    assert ctx["evidence_state"] == "E0_no_evidence"
    assert ctx["metadata"]["akta_evidence_state"] == "no_evidence"


def test_weak_alias_emits_quality_warning(tmp_path):
    engine = ScopeEngine.from_policy_dir(
        ROOT / "policy", ledger_path=tmp_path / "events.jsonl"
    )
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {"evidence_state": "E1_anecdotal"},
    }
    record = {"record_id": "AKTA-EV-ALIAS", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    assert packet["scientific_context"]["evidence_state"] == (
        "E1_anecdotal_or_informal_observation"
    )
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
