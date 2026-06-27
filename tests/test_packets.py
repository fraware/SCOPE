"""Tests for SCOPE packets."""

from pathlib import Path

from scope import ScopeEngine

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


def test_create_packet_from_akta():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    assert packet["packet_id"].startswith("SCOPE-PKT-")
    assert packet["review_request"]["required_review_roles"] == ["protocol_owner"]
    assert packet["review_request"]["akta_admissibility"] == "review_required"
    assert packet["packet_hash"].startswith("sha256:")


def test_validate_packet():
    engine = ScopeEngine.from_policy_dir(ROOT / "policy")
    packet = engine.create_packet(EX / "akta_record.json", EX / "review_trigger.json")
    engine.validate_packet(packet)
