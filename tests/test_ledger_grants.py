"""Tests for ledger-backed grant use and expiration (Priority 3)."""

from pathlib import Path

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def _make_grant(tmp_path):
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    ctx = {"protocol_version": "protocol_v3", "evidence_state": "E2_preliminary_signal"}
    return engine, grant, ctx, ledger


def test_single_use_once(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert engine.ledger.grant_used(grant["grant_id"])


def test_single_use_twice_blocked(tmp_path):
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_validation_run",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "single_validation_run_draft",
        "scientific_context": {
            "protocol_version": "protocol_v1",
            "evidence_state": "E1_hypothesis",
        },
    }
    packet = engine.create_packet({"record_id": "SU", **trigger}, {})
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "po", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_run_draft",
            "rationale": "once",
        },
    )
    grant = engine.issue_grant(packet, decision)
    ctx = {"protocol_version": "protocol_v1", "evidence_state": "E1_hypothesis"}
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert not engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    status = engine.grant_status(grant["grant_id"])
    assert status["used"]


def test_single_use_grant_not_reused_without_single_use_flag(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)


def test_revoked_grant_blocked(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    engine.revoke_grant(grant["grant_id"], reason="Policy change")
    assert not engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    status = engine.grant_status(grant["grant_id"])
    assert status["status"] == "revoked"


def test_protocol_version_change_expires(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    assert engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    stale = {**ctx, "protocol_version": "protocol_v4"}
    assert not engine.check_grant(grant, "protocol_editor.draft_change", stale)


def test_evidence_state_change_expires(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    grant["expiration"]["expires_after"] = ["evidence_state_change"]
    stale = {**ctx, "evidence_state": "E0_unknown"}
    assert not engine.check_grant(grant, "protocol_editor.draft_change", stale)


def test_grant_status_active(tmp_path):
    engine, grant, _, _ = _make_grant(tmp_path)
    status = engine.grant_status(grant["grant_id"])
    assert status["status"] == "active"
    assert not status["used"]


def test_quality_report_grant_counts(tmp_path):
    engine, grant, ctx, _ = _make_grant(tmp_path)
    engine.check_grant(grant, "protocol_editor.draft_change", ctx)
    report = engine.quality_report()
    assert report["summary"]["grant_use_count"] >= 1
    assert "by_reviewer" in report
    assert "by_role" in report
