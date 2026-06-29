"""Validate institutional pilot fixtures against engine output."""

import json
from pathlib import Path

from scope import ScopeEngine
from scope._version import __version__

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "examples" / "institutional_pilot"


def test_institutional_pilot_packet_regenerates():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    record = json.loads((PILOT / "akta_record.json").read_text(encoding="utf-8"))
    trigger = json.loads((PILOT / "review_trigger.json").read_text(encoding="utf-8"))
    packet = engine.create_packet(record, trigger)
    assert packet["review_request"]["scientific_action_type"] == "A5_protocol_modification"
    assert packet["packet_version"] == __version__
    fixture = json.loads((PILOT / "scope_packet.json").read_text(encoding="utf-8"))
    for key in (
        "packet_version",
        "review_request",
        "scientific_context",
        "akta_constraints",
    ):
        assert key in fixture
        assert key in packet


def test_institutional_pilot_grant_check_shape():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    grant = json.loads((PILOT / "scope_grant.json").read_text(encoding="utf-8"))
    decision = json.loads((PILOT / "scope_decision.json").read_text(encoding="utf-8"))
    context = json.loads((PILOT / "current_context.json").read_text(encoding="utf-8"))
    assert grant["provenance"]["scope_trust_root_hash"].startswith("sha256:")
    assert decision["provenance"]["scope_trust_root_hash"].startswith("sha256:")
    assert engine.policy.scope_trust_root_hash.startswith("sha256:")
    result = engine.check_grant_detailed(grant, "protocol_editor.draft_change", context)
    assert "allowed" in result
    assert "reason" in result
    assert "code" in result
