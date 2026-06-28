"""Tests for REST API (section 25 + v0.2 extensions)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.generic_rest.server import app
from scope._version import __version__
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "protocol_change_review"
DRIFT = ROOT / "examples" / "protocol_drift"


@pytest.fixture
def client():
    from adapters.generic_rest import server

    server.reset_engine_cache()
    yield TestClient(app)
    server.reset_engine_cache()


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
    assert body["version"] == __version__


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
    assert check["code"] == "allowed"


def test_grant_revoke_and_status(client, tmp_path, monkeypatch):
    ledger = tmp_path / "events.jsonl"
    monkeypatch.setenv("SCOPE_LEDGER_PATH", str(ledger))
    from adapters.generic_rest import server

    server.reset_engine_cache()

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


def test_rest_public_key_verify(client, tmp_path):
    from scope.signing import Ed25519Signer

    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    packet = client.post("/v0/packets", json=_packet_payload()).json()
    decision = client.post(
        "/v0/decisions",
        json={
            "packet": packet,
            "reviewer": _load("reviewer_protocol_owner.json"),
            "decision": _load("decision.json"),
        },
    ).json()
    signed = client.post(
        "/v0/decisions/sign",
        json={"artifact": decision, "key_path": str(key)},
    ).json()

    verify = client.post(
        "/v0/verify",
        json={
            "artifact": signed,
            "artifact_type": "decision",
            "public_key_path": str(pub),
        },
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True


def test_rest_persistent_session_store(client, tmp_path, monkeypatch):
    session_dir = tmp_path / "sessions"
    monkeypatch.setenv("SCOPE_SESSION_STORE", "json")
    monkeypatch.setenv("SCOPE_SESSION_DIR", str(session_dir))
    from adapters.generic_rest import server

    server.reset_engine_cache()

    trigger = {
        "akta_admissibility": "review_required",
        "scientific_action_type": "A6_experimental_planning",
        "requested_action": "plan_validation",
        "requested_tool": "experiment_planner.create_validation_plan",
        "requested_scope": "single_validation_plan",
    }
    record = {"record_id": "AKTA-REST-SESS", "scientific_action_type": "A6_experimental_planning"}
    packet = client.post(
        "/v0/packets",
        json={"akta_record": record, "akta_trigger": trigger},
    ).json()

    session = client.post("/v0/review-sessions", json={"packet": packet}).json()
    session_id = session["session_id"]

    vote = client.post(
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
    assert vote.status_code == 200

    server._engine = None
    status = client.get(f"/v0/review-sessions/{session_id}")
    assert status.status_code == 200
    assert len(status.json()["votes"]) == 1


def test_quality_endpoint(client):
    resp = client.get("/v0/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_version"] == "0.7"
    assert body["policy_version"] == "scope-core-v0.7"
    assert "metrics" in body
    assert "warnings" in body


def test_quality_endpoint_custom_queue_dir(client, tmp_path, monkeypatch):
    from adapters.generic_rest import server

    queue_dir = tmp_path / "custom_queues"
    monkeypatch.setenv("SCOPE_QUEUE_DIR", str(queue_dir))
    server._engine = None

    packet = client.post("/v0/packets", json=_packet_payload()).json()
    client.post(
        "/v0/review-queue",
        json={"packet": packet, "sla_hours": 24, "queue_dir": str(queue_dir)},
    )

    resp = client.get("/v0/quality", params={"queue_dir": str(queue_dir)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"]["open_queue_count"] >= 1


def test_akta_review_rest_endpoint(client, tmp_path):
    from adapters.generic_rest import server
    from scope.config import is_production_mode

    server.reset_engine_cache()
    out_dir = tmp_path / "akta_out"
    payload = {
        "akta_record": _load("akta_record.json", DRIFT),
        "akta_trigger": _load("review_trigger.json", DRIFT),
        "grant_scope": "protocol_draft",
        "reviewer": _load("reviewer_protocol_owner.json", DRIFT),
        "decision_rationale": "REST AKTA review path.",
        "out_dir": str(out_dir),
    }
    resp = client.post("/v0/akta/review", json=payload)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["status"] == "completed"
    assert summary["approved_scope"] == "protocol_draft"
    assert summary["scope_trust_root_hash"].startswith("sha256:")
    assert summary["identity_assurance_level"] == "IAL0"
    assert summary["signing_assurance_level"] == "SAL0"
    assert summary["production_mode"] is is_production_mode()
    assert (out_dir / "scope_grant.json").exists()


def test_drift_example_packet(client):
    payload = {
        "akta_record": _load("akta_record.json", DRIFT),
        "akta_trigger": _load("review_trigger.json", DRIFT),
    }
    packet = client.post("/v0/packets", json=payload).json()
    assert packet["review_request"]["requested_scope"] == "protocol_draft"


def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("SCOPE_API_KEY", "test-secret-key")
    from adapters.generic_rest import server

    server.reset_engine_cache()

    health = client.get("/v0/health")
    assert health.status_code == 200

    denied = client.post("/v0/packets", json=_packet_payload())
    assert denied.status_code == 401

    authorized = client.post(
        "/v0/packets",
        json=_packet_payload(),
        headers={"Authorization": "Bearer test-secret-key"},
    )
    assert authorized.status_code == 200


def test_grant_check_returns_reason_and_code(client):
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

    blocked = client.post(
        "/v0/grants/check",
        json={
            "grant": grant,
            "requested_tool": "robot_queue.submit",
            "context": _load("current_context.json"),
        },
    ).json()
    assert blocked["allowed"] is False
    assert blocked["code"] == "tool_blocked"
    assert "blocked" in blocked["reason"].lower()

    expired_ctx = {**_load("current_context.json"), "protocol_version": "protocol_v99"}
    expired = client.post(
        "/v0/grants/check",
        json={
            "grant": grant,
            "requested_tool": "protocol_editor.draft_change",
            "context": expired_ctx,
        },
    ).json()
    assert expired["allowed"] is False
    assert expired["code"] == "grant_expired"
    assert expired["reason"]


def test_review_queue_rest_endpoints(client, tmp_path, monkeypatch):
    from adapters.generic_rest import server

    queue_dir = tmp_path / "queues"
    monkeypatch.setenv("SCOPE_QUEUE_DIR", str(queue_dir))
    server._engine = None

    packet = client.post("/v0/packets", json=_packet_payload()).json()
    created = client.post(
        "/v0/review-queue",
        json={"packet": packet, "sla_hours": 24, "queue_dir": str(queue_dir)},
    )
    assert created.status_code == 200
    queue_id = created.json()["queue_id"]

    assigned = client.post(
        f"/v0/review-queue/{queue_id}/assign",
        json={"reviewer": {"reviewer_id": "r1", "role": "protocol_owner"}},
        params={"queue_dir": str(queue_dir)},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"

    in_review = client.post(
        f"/v0/review-queue/{queue_id}/in-review",
        params={"queue_dir": str(queue_dir)},
    )
    assert in_review.status_code == 200
    assert in_review.json()["status"] == "in_review"

    needs_info = client.post(
        f"/v0/review-queue/{queue_id}/needs-information",
        json={"reason": "missing protocol appendix"},
        params={"queue_dir": str(queue_dir)},
    )
    assert needs_info.status_code == 200
    assert needs_info.json()["status"] == "needs_information"

    info_received = client.post(
        f"/v0/review-queue/{queue_id}/information-received",
        params={"queue_dir": str(queue_dir)},
    )
    assert info_received.status_code == 200
    assert info_received.json()["status"] == "in_review"

    expired = client.post(
        f"/v0/review-queue/{queue_id}/expire",
        params={"queue_dir": str(queue_dir)},
    )
    assert expired.status_code == 200
    assert expired.json()["status"] == "expired"

    reopened = client.post(
        f"/v0/review-queue/{queue_id}/reopen",
        params={"queue_dir": str(queue_dir)},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"

    assigned_again = client.post(
        f"/v0/review-queue/{queue_id}/assign",
        json={"reviewer": {"reviewer_id": "r1", "role": "protocol_owner"}},
        params={"queue_dir": str(queue_dir)},
    )
    assert assigned_again.status_code == 200

    escalated = client.post(
        f"/v0/review-queue/{queue_id}/escalate",
        json={
            "reviewer": {"reviewer_id": "lead1", "role": "lab_operations_lead"},
            "reason": "SLA breach",
            "actor_id": "ops-bot",
        },
        params={"queue_dir": str(queue_dir)},
    )
    assert escalated.status_code == 200
    assert escalated.json()["status"] == "escalated"

    cancelled = client.post(
        f"/v0/review-queue/{queue_id}/cancel",
        json={"reason": "duplicate request"},
        params={"queue_dir": str(queue_dir)},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    listed = client.get("/v0/review-queue", params={"queue_dir": str(queue_dir)})
    assert listed.status_code == 200
    counts = listed.json()["status_counts"]
    assert counts.get("cancelled", 0) >= 1


def test_review_queue_invalid_transition_rest_error(client, tmp_path, monkeypatch):
    from adapters.generic_rest import server

    queue_dir = tmp_path / "queues"
    server._engine = None

    packet = client.post("/v0/packets", json=_packet_payload()).json()
    created = client.post(
        "/v0/review-queue",
        json={"packet": packet, "sla_hours": 24, "queue_dir": str(queue_dir)},
    )
    queue_id = created.json()["queue_id"]

    resp = client.post(
        f"/v0/review-queue/{queue_id}/grant",
        json={"grant_id": "SCOPE-GRANT-BAD"},
        params={"queue_dir": str(queue_dir)},
    )
    assert resp.status_code == 400
    assert "expected decided" in resp.json()["detail"]


def test_key_registry_rest_endpoints(client, tmp_path, monkeypatch):
    from adapters.generic_rest import server

    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    monkeypatch.setenv("SCOPE_POLICY_DIR", str(policy_copy))
    server._engine = None

    pub = tmp_path / "reviewer.pub"
    key = tmp_path / "reviewer.pem"
    Ed25519Signer.generate_keypair(key, pub)

    registered = client.post(
        "/v0/keys/register",
        json={
            "reviewer_id": "rest_rev",
            "public_key_path": str(pub),
        },
    )
    assert registered.status_code == 200

    listed = client.get("/v0/keys")
    assert listed.status_code == 200
    assert listed.json()["reviewer_count"] == 1

