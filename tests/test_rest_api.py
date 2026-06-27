"""Tests for REST API (section 25)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.generic_rest.server import app

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"


@pytest.fixture
def client():
    return TestClient(app)


def _load(name: str) -> dict:
    return json.loads((EX / name).read_text(encoding="utf-8"))


def _packet_payload() -> dict:
    return {
        "akta_record": _load("akta_record.json"),
        "akta_trigger": _load("review_trigger.json"),
    }


def test_health(client):
    resp = client.get("/v0/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_packet_create_and_validate(client):
    resp = client.post("/v0/packets", json=_packet_payload())
    assert resp.status_code == 200
    packet = resp.json()
    assert packet["packet_id"].startswith("SCOPE-PKT-")

    vresp = client.post("/v0/packets/validate", json=packet)
    assert vresp.status_code == 200
    assert vresp.json()["status"] == "valid"


def test_decision_grant_check_flow(client):
    packet = client.post("/v0/packets", json=_packet_payload()).json()
    decision = client.post(
        "/v0/decisions",
        json={
            "packet": packet,
            "reviewer": _load("reviewer_protocol_owner.json"),
            "decision": _load("decision.json"),
        },
    ).json()
    grant = client.post(
        "/v0/grants",
        json={"packet": packet, "decision": decision},
    ).json()
    check = client.post(
        "/v0/grants/check",
        json={
            "grant": grant,
            "requested_tool": "protocol_editor.draft_change",
            "context": _load("current_context.json"),
        },
    ).json()
    assert check["allowed"] is True


def test_export_endpoints(client):
    packet = client.post("/v0/packets", json=_packet_payload()).json()
    decision = client.post(
        "/v0/decisions",
        json={
            "packet": packet,
            "reviewer": _load("reviewer_protocol_owner.json"),
            "decision": _load("decision.json"),
        },
    ).json()
    grant = client.post(
        "/v0/grants",
        json={"packet": packet, "decision": decision},
    ).json()

    pf = client.post("/v0/export/pf", json=grant)
    assert pf.status_code == 200
    assert "protocol_editor.draft_change" in pf.json()["permitted_tools"]

    pcs = client.post(
        "/v0/export/pcs",
        json={"packet": packet, "decision": decision, "grant": grant},
    )
    assert pcs.status_code == 200
    assert "path" in pcs.json()


def test_quality_endpoint(client):
    resp = client.get("/v0/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert "metrics" in body
    assert "warnings" in body
