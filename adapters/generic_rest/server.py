"""Optional FastAPI REST server for SCOPE v0.2."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from scope import ScopeEngine
from scope.errors import GrantValidationError, ScopeValidationError
from scope.render import render_html, render_markdown
from scope.signing import Ed25519Signer

app = FastAPI(title="SCOPE REST API", version="0.2.0")
_engine: ScopeEngine | None = None
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def get_engine() -> ScopeEngine:
    global _engine
    if _engine is None:
        policy = Path(__file__).resolve().parents[2] / "policy"
        ledger = os.environ.get("SCOPE_LEDGER_PATH")
        _engine = ScopeEngine.from_policy_dir(policy, ledger_path=ledger)
    return _engine


def _signer_from_env(explicit: str | None = None) -> Ed25519Signer:
    key_path = explicit or os.environ.get("SCOPE_SIGNING_KEY")
    if not key_path:
        raise HTTPException(
            status_code=400,
            detail="Signing key required via request key_path or SCOPE_SIGNING_KEY",
        )
    return Ed25519Signer(key_path)


class PacketCreateRequest(BaseModel):
    akta_record: dict[str, Any]
    akta_trigger: dict[str, Any]


class PacketRenderRequest(BaseModel):
    packet: dict[str, Any]
    format: Literal["markdown", "html"] = "markdown"


class DecisionRequest(BaseModel):
    packet: dict[str, Any]
    reviewer: dict[str, Any]
    decision: dict[str, Any]


class SignRequest(BaseModel):
    artifact: dict[str, Any]
    key_path: str | None = None


class VerifyRequest(BaseModel):
    artifact: dict[str, Any]
    artifact_type: Literal["decision", "grant"]
    key_path: str | None = None


class GrantIssueRequest(BaseModel):
    packet: dict[str, Any]
    decision: dict[str, Any]


class GrantCheckRequest(BaseModel):
    grant: dict[str, Any]
    requested_tool: str
    context: dict[str, Any] | None = None


class GrantRevokeRequest(BaseModel):
    grant_id: str
    reason: str = "Manual revocation"


class ReviewSessionCreateRequest(BaseModel):
    packet: dict[str, Any]
    quorum_policy: dict[str, Any] | None = None


class ReviewSessionVoteRequest(BaseModel):
    packet: dict[str, Any]
    reviewer: dict[str, Any]
    decision: dict[str, Any]


class ReviewSessionGrantRequest(BaseModel):
    packet: dict[str, Any]
    decisions: list[dict[str, Any]]


class PcsExportRequest(BaseModel):
    packet: dict[str, Any]
    decision: dict[str, Any]
    grant: dict[str, Any]
    run_validation: bool = False


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ScopeValidationError, GrantValidationError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/v0/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.2.0"}


@app.post("/v0/packets")
def create_packet(req: PacketCreateRequest) -> dict[str, Any]:
    return get_engine().create_packet(req.akta_record, req.akta_trigger)


@app.post("/v0/packets/validate")
def validate_packet(packet: dict[str, Any]) -> dict[str, str]:
    get_engine().validate_packet(packet)
    return {"status": "valid"}


@app.post("/v0/packets/render")
def render_packet(req: PacketRenderRequest) -> dict[str, str]:
    content = render_html(req.packet) if req.format == "html" else render_markdown(req.packet)
    return {"format": req.format, "content": content}


@app.post("/v0/decisions")
def submit_decision(req: DecisionRequest) -> dict[str, Any]:
    try:
        return get_engine().submit_decision(req.packet, req.reviewer, req.decision)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/decisions/sign")
def sign_decision(req: SignRequest) -> dict[str, Any]:
    try:
        signer = _signer_from_env(req.key_path)
        return get_engine().sign_decision(req.artifact, signer)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/review-sessions")
def create_review_session(req: ReviewSessionCreateRequest) -> dict[str, Any]:
    session = get_engine().create_review_session(req.packet, quorum_policy=req.quorum_policy)
    return session.to_artifact()


@app.get("/v0/review-sessions/{session_id}")
def get_review_session(session_id: str) -> dict[str, Any]:
    try:
        return get_engine().get_review_session(session_id).to_artifact()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v0/review-sessions/{session_id}/votes")
def submit_review_vote(session_id: str, req: ReviewSessionVoteRequest) -> dict[str, Any]:
    try:
        session = get_engine().get_review_session(session_id)
        decision = get_engine().submit_session_decision(
            session, req.packet, req.reviewer, req.decision
        )
        return {"decision": decision, "session": session.to_artifact()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/review-sessions/{session_id}/grants")
def issue_grant_from_session(session_id: str, req: ReviewSessionGrantRequest) -> dict[str, Any]:
    try:
        session = get_engine().get_review_session(session_id)
        return get_engine().issue_grant_from_session(session, req.packet, req.decisions)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/grants")
def issue_grant(req: GrantIssueRequest) -> dict[str, Any]:
    try:
        return get_engine().issue_grant(req.packet, req.decision)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/grants/check")
def check_grant(req: GrantCheckRequest) -> dict[str, Any]:
    ok = get_engine().check_grant(req.grant, req.requested_tool, req.context)
    return {"allowed": ok}


@app.post("/v0/grants/revoke")
def revoke_grant(req: GrantRevokeRequest) -> dict[str, Any]:
    return get_engine().revoke_grant(req.grant_id, reason=req.reason)


@app.get("/v0/grants/{grant_id}/status")
def grant_status(grant_id: str) -> dict[str, Any]:
    return get_engine().grant_status(grant_id)


@app.post("/v0/grants/sign")
def sign_grant(req: SignRequest) -> dict[str, Any]:
    try:
        signer = _signer_from_env(req.key_path)
        return get_engine().sign_grant(req.artifact, signer)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/verify")
def verify_artifact(req: VerifyRequest) -> dict[str, bool]:
    try:
        signer = _signer_from_env(req.key_path)
        engine = get_engine()
        ok = (
            engine.verify_decision(req.artifact, signer)
            if req.artifact_type == "decision"
            else engine.verify_grant(req.artifact, signer)
        )
        return {"valid": ok}
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/v0/quality")
def quality() -> dict[str, Any]:
    return get_engine().quality_report()


@app.post("/v0/export/pf")
def export_pf(grant: dict[str, Any]) -> dict[str, Any]:
    from adapters.pf_core.export_obligation import export_pf_obligation

    return export_pf_obligation(grant)


@app.post("/v0/export/pf/validate")
def validate_pf_export_endpoint(body: dict[str, Any]) -> dict[str, str]:
    from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export

    grant = body["grant"]
    obligation = body.get("obligation") or export_pf_obligation(grant)
    schema = _SCHEMAS_DIR / "pf_scope_obligation.schema.json"
    validate_pf_export(obligation, grant, schema if schema.exists() else None)
    return {"status": "valid"}


@app.post("/v0/export/pcs")
def export_pcs(req: PcsExportRequest) -> dict[str, str]:
    from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export

    engine = get_engine()
    tmp = Path(tempfile.mkdtemp(prefix="scope_pcs_"))
    export_pcs_artifact(
        req.packet,
        req.decision,
        req.grant,
        tmp,
        ledger_events=engine.ledger.events(),
        quality_warnings=engine.quality_report().get("warnings", []),
    )
    if req.run_validation:
        schema = _SCHEMAS_DIR / "pcs_scope_artifact.schema.json"
        validate_pcs_export(tmp, schema if schema.exists() else None)
    return {"path": str(tmp), "validated": str(req.run_validation).lower()}


@app.post("/v0/export/pcs/validate")
def validate_pcs_export_endpoint(body: dict[str, Any]) -> dict[str, str]:
    from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export

    engine = get_engine()
    tmp = Path(tempfile.mkdtemp(prefix="scope_pcs_validate_"))
    export_pcs_artifact(
        body["packet"],
        body["decision"],
        body["grant"],
        tmp,
        ledger_events=engine.ledger.events(),
        quality_warnings=engine.quality_report().get("warnings", []),
    )
    schema = _SCHEMAS_DIR / "pcs_scope_artifact.schema.json"
    validate_pcs_export(tmp, schema if schema.exists() else None)
    return {"status": "valid", "path": str(tmp)}
