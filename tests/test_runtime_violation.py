"""Tests for runtime violation ledger recording."""

from __future__ import annotations

import tempfile
from pathlib import Path

from scope import ScopeEngine


def test_record_runtime_violation_metric() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "ledger.jsonl"
        engine = ScopeEngine.from_policy_dir("policy/", ledger_path=ledger)
        event = engine.record_runtime_violation(
            "SCOPE-GRANT-TEST",
            tool="robot.submit",
            reason="Out of scope tool invocation",
        )
        assert event["event_type"] == "runtime_scope_violation"
        report = engine.quality_report()
        assert report["metrics"]["runtime_violation_outcome_count"] >= 1
