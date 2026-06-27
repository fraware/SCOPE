"""Tests for grant expiration."""

from pathlib import Path

from scope.expiration import is_expired

ROOT = Path(__file__).resolve().parent.parent


def test_protocol_version_expiration():
    grant = {
        "constraints": {"protocol_version": "protocol_v3"},
        "expiration": {"expires_after": ["protocol_version_change"]},
    }
    assert not is_expired(grant, {"protocol_version": "protocol_v3"})
    assert is_expired(grant, {"protocol_version": "protocol_v4"})


def test_single_use_expiration():
    grant = {
        "constraints": {"single_use": True},
        "expiration": {"expires_after": ["single_use"]},
    }
    assert is_expired(grant, {"grant_used": True})
