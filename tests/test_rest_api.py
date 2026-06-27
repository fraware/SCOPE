"""Tests for REST API (section 25 + v0.2 extensions)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.generic_rest.server import app

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"
DRIFT = ROOT / "examples" / "protocol_drift"


@pytest.fixture
def client():
    return TestClient(app)


def _load(name: str, base: Path = EX) -> dict:
    return json.loads((base / name).read_text(encoding="utf-8"))


def _packet_payload() -> dict:
    return {
        "akta_record": _load("akta_record.json"),
        "akta_trigger": _load("review_trigger.json"),
    }


def test_health(client):
    resp = client.get("/v0/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.2.0"


def test_packet_create_and_validate(client):
    resp = client.post("/v0/packets", json=_packet_payload())
    assert resp.status_code == 200
    packet = resp.json()
    assert packet["packet_id"].startswith("SCOPE-PKT-")

    vresp = client.post("/v0/packets/validate", json=packet)
    assert vresp.status_code == 200
    assert vresp.json()["status"] == "valid"


def test_packet_render(client):
    packet = client.post("/v0/packets", json=_packet_payload()).json()
    resp = client.post("/v0/packets/render", json={"packet": packet, "format": "markdown"})
    assert resp.status_code == 200
    content = resp.json()["content"]
    assert packet["packet_id"] in content
    assert "SCOPE Review Packet" in content


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


def test_grant_revoke_and_status(client, tmp_path, monkeypatch):
    ledger = tmp_path / "events.jsonl"
    monkeypatch.setenv("SCOPE_LEDGER_PATH", str(ledger))
    from adapters.generic_rest import server

    server._engine = None

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

    status = client.get(f"/v0/grants/{grant['grant_id']}/status")
    assert status.status_code == 200
    assert status.json()["status"] == "active"

    revoke = client.post(
        "/v0/grants/revoke",
        json={"grant_id": grant["grant_id"], "reason": "test revoke"},
    )
    assert revoke.status_code == 200

    status2 = client.get(f"/v0/grants/{grant['grant_id']}/status")
    assert status2.json()["status"] == "revoked"


def test_review_session_flow(client):
    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
        "scientific_context": {"protocol_version": "protocol_v1"},
    }
    record = {"record_id": "AKTA-A6", "scientific_action_type": "A6_experimental_planning"}
    packet = client.post(
        "/v0/packets",
        json={"akta_record": record, "akta_trigger": trigger},
    ).json()

    session = client.post("/v0/review-sessions", json={"packet": packet}).json()
    session_id = session["session_id"]
    assert session["status"] == "pending"

    vote1 = client.post(
        f"/v0/review-sessions/{session_id}/votes",
        json={
            "packet": packet,
            "reviewer": {"reviewer_id": "ds1", "role": "domain_scientist"},
            "decision": {
                "type": "approve_narrower_scope",
                "approved_scope": "single_validation_plan",
                "rationale": "ok",
            },
        },
    )
    assert vote1.status_code == 200

    vote2 = client.post(
        f"/v0/review-sessions/{session_id}/votes",
        json={
            "packet": packet,
            "reviewer": {"reviewer_id": "po1", "role": "protocol_owner"},
            "decision": {
                "type": "approve_narrower_scope",
                "approved_scope": "single_validation_plan",
                "rationale": "ok",
            },
        },
    )
    assert vote2.status_code == 200

    status = client.get(f"/v0/review-sessions/{session_id}")
    assert status.json()["status"] == "quorum_met"

    grant = client.post(
        f"/v0/review-sessions/{session_id}/grants",
        json={
            "packet": packet,
            "decisions": [vote1.json()["decision"], vote2.json()["decision"]],
        },
    )
    assert grant.status_code == 200
    assert grant.json()["authorization"]["approved_scope"] == "single_validation_plan"


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

    pf_val = client.post("/v0/export/pf/validate", json={"grant": grant})
    assert pf_val.status_code == 200
    assert pf_val.json()["status"] == "valid"

    pcs = client.post(
        "/v0/export/pcs",
        json={"packet": packet, "decision": decision, "grant": grant, "run_validation": True},
    )
    assert pcs.status_code == 200
    assert pcs.json()["validated"] == "true"

    pcs_val = client.post(
        "/v0/export/pcs/validate",
        json={"packet": packet, "decision": decision, "grant": grant},
    )
    assert pcs_val.status_code == 200
    assert pcs_val.json()["status"] == "valid"


def test_sign_and_verify(client, tmp_path, monkeypatch):
    from scope.signing import Ed25519Signer

    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)
    monkeypatch.setenv("SCOPE_SIGNING_KEY", str(key))

    packet = client.post("/v0/packets", json=_packet_payload()).json()
    decision = client.post(
        "/v0/decisions",
        json={
            "packet": packet,
            "reviewer": _load("reviewer_protocol_owner.json"),
            "decision": _load("decision.json"),
        },
    ).json()
    signed = client.post("/v0/decisions/sign", json={"artifact": decision})
    assert signed.status_code == 200
    assert signed.json()["decision_signature"]

    verify = client.post(
        "/v0/verify",
        json={"artifact": signed.json(), "artifact_type": "decision"},
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True


def test_quality_endpoint(client):
    resp = client.get("/v0/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_version"] == "0.2"
    assert body["policy_version"] == "scope-core-v0.2"
    assert "metrics" in body
    assert "warnings" in body


def test_drift_example_packet(client):
    payload = {
        "akta_record": _load("akta_record.json", DRIFT),
        "akta_trigger": _load("review_trigger.json", DRIFT),
    }
    packet = client.post("/v0/packets", json=payload).json()
    assert packet["review_request"]["requested_scope"] == "protocol_draft"
