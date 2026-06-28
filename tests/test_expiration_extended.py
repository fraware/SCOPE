"""Tests for extended expiration rules."""

from pathlib import Path

from scope.expiration import is_expired


def test_domain_overlay_change():
    grant = {
        "constraints": {"domain_overlay": "genomics_research"},
        "expiration": {"expires_after": ["domain_overlay_change"]},
    }
    assert not is_expired(grant, {"domain_overlay": "genomics_research"})
    assert is_expired(grant, {"domain_overlay": "clinical_trials"})


def test_model_version_change():
    grant = {
        "constraints": {"model_version": "model_v1"},
        "expiration": {"expires_after": ["model_version_change"]},
    }
    assert not is_expired(grant, {"model_version": "model_v1"})
    assert is_expired(grant, {"model_version": "model_v2"})


def test_tool_registry_change():
    grant = {
        "constraints": {"tool_registry_version": "registry_v1"},
        "expiration": {"expires_after": ["tool_registry_change"]},
    }
    assert not is_expired(grant, {"tool_registry_version": "registry_v1"})
    assert is_expired(grant, {"tool_registry_version": "registry_v2"})


def test_reviewer_withdrawal():
    grant = {"expiration": {"expires_after": ["reviewer_withdrawal"]}}
    assert is_expired(grant, {"reviewer_withdrawal": True})


def test_completion_of_single_validation_run():
    grant = {"expiration": {"expires_after": ["completion_of_single_validation_run"]}}
    assert not is_expired(grant, {})
    assert is_expired(grant, {"validation_run_completed": True})


def _grant_engine(tmp_path):
    from scope import ScopeEngine

    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(
        Path(__file__).resolve().parent.parent / "policy", ledger_path=ledger
    )
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
        "scientific_context": {
            "domain_overlay": "genomics_research",
            "model_version": "model_v1",
            "tool_registry_version": "registry_v1",
            "protocol_version": "protocol_v1",
        },
    }
    record = {"record_id": "AKTA-EXP", "scientific_action_type": "A5_protocol_modification"}
    packet = engine.create_packet(record, trigger)
    decision = engine.submit_decision(
        packet,
        {"reviewer_id": "r1", "role": "protocol_owner"},
        {"type": "approve_narrower_scope", "approved_scope": "protocol_draft", "rationale": "ok"},
    )
    grant = engine.issue_grant(packet, decision)
    grant["expiration"]["expires_after"] = [
        "domain_overlay_change",
        "model_version_change",
        "tool_registry_change",
        "reviewer_withdrawal",
        "completion_of_single_validation_run",
    ]
    ctx = {
        "domain_overlay": "genomics_research",
        "model_version": "model_v1",
        "tool_registry_version": "registry_v1",
        "protocol_version": "protocol_v1",
    }
    return engine, grant, ctx


def test_extended_triggers_wired_from_grant_check_context(tmp_path):
    engine, grant, ctx = _grant_engine(tmp_path)
    tool = "protocol_editor.draft_change"

    assert engine.check_grant(grant, tool, ctx)
    assert not engine.check_grant(grant, tool, {**ctx, "domain_overlay": "clinical_trials"})
    assert not engine.check_grant(grant, tool, {**ctx, "model_version": "model_v2"})
    assert not engine.check_grant(grant, tool, {**ctx, "tool_registry_version": "registry_v2"})
    assert not engine.check_grant(grant, tool, {**ctx, "reviewer_withdrawal": True})
    assert not engine.check_grant(
        grant, tool, {**ctx, "validation_run_completed": True}
    )

    results = [
        engine.check_grant_detailed(grant, tool, {**ctx, "domain_overlay": "clinical_trials"}),
        engine.check_grant_detailed(grant, tool, {**ctx, "model_version": "model_v2"}),
    ]
    for result in results:
        assert result["allowed"] is False
        assert result["code"] == "grant_expired"
        assert result["reason"]
