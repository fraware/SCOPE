"""Tests for SessionStore abstraction (SCOPE-3)."""

from pathlib import Path

import pytest

from scope import ScopeEngine, create_session_store
from scope.errors import DecisionValidationError
from scope.session_store import JsonFileSessionStore, MemorySessionStore, SQLiteSessionStore

ROOT = Path(__file__).resolve().parent.parent


def _a6_packet(engine):
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "scientific_context": {"protocol_version": "protocol_v1"},
    }
    record = {"record_id": "AKTA-SESS", "scientific_action_type": "A6_experimental_planning"}
    return engine.create_packet(record, trigger)


@pytest.mark.parametrize("store_type", ["memory", "json", "sqlite"])
def test_session_survives_restart(tmp_path, store_type):
    session_dir = tmp_path / "sessions"
    if store_type == "sqlite":
        session_dir = tmp_path / "sessions.db"
    store = create_session_store(store_type, session_dir)
    ledger = tmp_path / "events.jsonl"

    engine1 = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger, session_store=store)
    packet = _a6_packet(engine1)
    session = engine1.create_review_session(packet)
    session_id = session.session_id

    engine2 = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger, session_store=store)
    restored = engine2.get_review_session(session_id, packet)
    assert restored.session_id == session_id
    assert restored.votes == []

    d1 = engine2.submit_session_decision(
        restored,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    d2 = engine2.submit_session_decision(
        restored,
        packet,
        {"reviewer_id": "po1", "role": "protocol_owner"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    grant = engine2.issue_grant_from_session(restored, packet, [d1, d2])
    assert grant["authorization"]["approved_scope"] == "single_validation_plan"

    status = engine2.session_status(session_id)
    assert status["status"] == "quorum_met"
    assert len(status["votes"]) == 2


def test_replace_vote(tmp_path):
    store = JsonFileSessionStore(tmp_path / "sessions")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", session_store=store)
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "first",
        },
    )
    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "revised rationale only",
        },
        replace_vote=True,
    )
    status = engine.session_status(session.session_id)
    assert len(status["votes"]) == 1
    assert status["votes"][0]["approved_scope"] == "single_validation_plan"


def test_get_session_from_snapshot_only(tmp_path):
    store = JsonFileSessionStore(tmp_path / "sessions")
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", session_store=store)
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    restored = engine.get_review_session(session.session_id)
    assert restored.packet_snapshot["packet_id"] == packet["packet_id"]


def test_duplicate_vote_rejected():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)
    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )
    with pytest.raises(DecisionValidationError, match="Duplicate vote"):
        engine.submit_session_decision(
            session,
            packet,
            {"reviewer_id": "ds1", "role": "domain_scientist"},
            {
                "type": "approve_narrower_scope",
                "approved_scope": "single_validation_plan",
                "rationale": "duplicate",
            },
        )


def test_json_file_store_load_missing():
    store = JsonFileSessionStore(Path("/tmp/nonexistent_scope_test_dir"))
    with pytest.raises(KeyError):
        store.load("SCOPE-SESS-MISSING")


def test_sqlite_store_exists(tmp_path):
    db = tmp_path / "test.db"
    store = SQLiteSessionStore(db)
    assert not store.exists("SCOPE-SESS-X")
    store.save(_minimal_session_artifact("SCOPE-SESS-X"))
    assert store.exists("SCOPE-SESS-X")


def _minimal_session_artifact(session_id: str = "SCOPE-SESS-X") -> dict:
    return {
        "session_id": session_id,
        "session_version": "0.5.0",
        "packet_id": "P1",
        "scientific_action_type": "A6_experimental_planning",
        "quorum_policy": {"mode": "require_all", "required_roles": ["domain_scientist"]},
        "required_roles": ["domain_scientist"],
        "votes": [],
        "created_at": "2026-01-01T00:00:00Z",
        "status": "pending",
        "packet_snapshot": {
            "packet_id": "P1",
            "review_request": {"scientific_action_type": "A6_experimental_planning"},
        },
    }


def test_memory_store_roundtrip():
    store = MemorySessionStore()
    artifact = _minimal_session_artifact("SCOPE-SESS-M1")
    store.save(artifact)
    assert store.load("SCOPE-SESS-M1")["session_id"] == "SCOPE-SESS-M1"


def test_ledger_and_session_store_consistent(tmp_path):
    session_dir = tmp_path / "sessions"
    store = JsonFileSessionStore(session_dir)
    ledger = tmp_path / "events.jsonl"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger, session_store=store)
    packet = _a6_packet(engine)
    session = engine.create_review_session(packet)

    engine.submit_session_decision(
        session,
        packet,
        {"reviewer_id": "ds1", "role": "domain_scientist"},
        {
            "type": "approve_narrower_scope",
            "approved_scope": "single_validation_plan",
            "rationale": "ok",
        },
    )

    status = engine.session_status(session.session_id)
    assert len(status["votes"]) == 1
    assert status["votes"][0]["reviewer_id"] == "ds1"

    vote_events = [
        e for e in engine.ledger.events() if e.get("event_type") == "reviewer_vote_recorded"
    ]
    assert len(vote_events) == 1
    assert vote_events[0]["metadata"]["session_id"] == session.session_id
    assert vote_events[0]["actor_id"] == "ds1"
