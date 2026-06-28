"""Tests for quality report --queue-dir wiring (v0.5.1)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scope import ScopeEngine
from scope.cli import main
from scope.review_queue import DEFAULT_QUEUE_DIR

ROOT = Path(__file__).resolve().parent.parent


def _sample_packet(engine: ScopeEngine) -> dict:
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A5_protocol_modification",
        "requested_action": "draft_protocol",
        "requested_tool": "protocol_editor.draft_change",
        "requested_scope": "protocol_draft",
    }
    record = {"record_id": "AKTA-QQ", "scientific_action_type": "A5_protocol_modification"}
    return engine.create_packet(record, trigger)


def test_quality_report_default_queue_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ledger = tmp_path / "events.jsonl"
    default_dir = tmp_path / DEFAULT_QUEUE_DIR
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = _sample_packet(engine)
    engine.create_review_queue(packet, queue_dir=default_dir)

    report = engine.quality_report()
    assert report["metrics"]["open_queue_count"] == 1

    out = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "quality",
            "report",
            "--ledger",
            str(ledger),
            "--out",
            str(out),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["metrics"]["open_queue_count"] == 1


def test_quality_report_custom_queue_dir(tmp_path):
    ledger = tmp_path / "events.jsonl"
    queue_dir = tmp_path / "custom_queues"
    engine = ScopeEngine.from_policy_dir(ROOT / "policy", ledger_path=ledger)
    packet = _sample_packet(engine)
    engine.create_review_queue(packet, queue_dir=queue_dir)

    report = engine.quality_report(queue_dir=queue_dir)
    assert report["metrics"]["open_queue_count"] == 1

    out = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "quality",
            "report",
            "--ledger",
            str(ledger),
            "--out",
            str(out),
            "--queue-dir",
            str(queue_dir),
            "--policy",
            str(ROOT / "policy"),
        ],
    )
    assert result.exit_code == 0, result.output
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["summary"]["open_queue_count"] == 1
