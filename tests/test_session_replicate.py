"""Tests for session replication."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scope import ScopeEngine
from scope.session_store import JsonFileSessionStore, replicate_sessions


def test_replicate_sessions_copies_files() -> None:
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        engine = ScopeEngine.from_policy_dir("policy/")
        packet = engine.create_packet(
            {"record_id": "R-REP", "scientific_action_type": "A6_experimental_planning"},
            {
                "akta_admissibility": "review_required",
                "scientific_action_type": "A6_experimental_planning",
                "requested_action": "plan_validation",
                "requested_tool": "experiment_planner.create_validation_plan",
                "requested_scope": "single_validation_plan",
            },
        )
        session = engine.create_review_session(packet)
        store = JsonFileSessionStore(src)
        store.save(session.to_artifact())
        result = replicate_sessions(src, dst)
        assert result["copied"] == 1
        copied = json.loads(
            (Path(dst) / f"{session.session_id}.json").read_text(encoding="utf-8")
        )
        assert copied["session_id"] == session.session_id
