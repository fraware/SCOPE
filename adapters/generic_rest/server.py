"""Optional FastAPI REST server for SCOPE."""

from __future__ import annotations

import os
import tempfile
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from scope import ScopeEngine
from scope._version import __version__
from scope.config import api_key
from scope.engine_factory import EngineFactory
from scope.errors import GrantValidationError, ScopeValidationError
from scope.render import render_html, render_markdown
from scope.signing import Ed25519PublicVerifier, Ed25519Signer

app = FastAPI(title="SCOPE REST API", version=__version__)
_engine_factory = EngineFactory()
_engine: ScopeEngine | None = None
_request_context: ContextVar[Request | None] = ContextVar("scope_request", default=None)
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _require_api_key(request: Request) -> None:
    expected = api_key()
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {expected}":
        return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_engine(request: Request | None = None) -> ScopeEngine:
    global _engine
    active = request or _request_context.get()
    if active is not None:
        return _engine_factory.from_headers(dict(active.headers))
    if _engine is None:
        _engine = _engine_factory.default_engine()
    return _engine


def reset_engine_cache() -> None:
    """Clear cached engines (for tests)."""
    global _engine
    _engine = None
    _engine_factory.clear_cache()


@app.middleware("http")
async def _scope_request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    token = _request_context.set(request)
    try:
        response = await call_next(request)
        _audit_rest_request(request, response.status_code)
        return response
    finally:
        _request_context.reset(token)


def _audit_rest_request(request: Request, status_code: int) -> None:
    """Append REST API audit event to ledger when enabled."""
    if os.environ.get("SCOPE_REST_AUDIT", "true").lower() in ("0", "false", "no"):
        return
    if request.url.path in ("/docs", "/openapi.json", "/redoc"):
        return
    try:
        engine = get_engine(request)
        caller_hdr = request.headers.get("x-scope-caller-id")
        caller = caller_hdr or (request.client.host if request.client else "unknown")
        tenant = request.headers.get("x-scope-tenant-id")
        engine.ledger.append(
            "rest_api_audit",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "caller": caller,
                "tenant_id": tenant,
            },
        )
    except Exception:
        pass


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
    vsa_report: dict[str, Any] | None = None


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
    public_key_path: str | None = None


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
    reviewer_withdrawal: bool = False


class ReviewSessionCreateRequest(BaseModel):
    packet: dict[str, Any]
    quorum_policy: dict[str, Any] | None = None


class ReviewSessionVoteRequest(BaseModel):
    packet: dict[str, Any]
    reviewer: dict[str, Any]
    decision: dict[str, Any]
    replace_vote: bool = False


class ReviewSessionGrantRequest(BaseModel):
    packet: dict[str, Any]
    decisions: list[dict[str, Any]]


class PcsExportRequest(BaseModel):
    packet: dict[str, Any]
    decision: dict[str, Any]
    grant: dict[str, Any]
    run_validation: bool = False


class ReviewQueueCreateRequest(BaseModel):
    packet: dict[str, Any]
    sla_hours: int = 72
    queue_dir: str | None = None
    auto_assign: bool = False


class LedgerViolationRequest(BaseModel):
    grant_id: str
    tool: str
    reason: str


class LedgerExpirationRequest(BaseModel):
    grant_id: str
    reason: str
    packet_id: str | None = None


class IdentityVerifyRequest(BaseModel):
    token: str


class ReviewQueueAssignRequest(BaseModel):
    reviewer: dict[str, Any]


class ReviewQueueDecideRequest(BaseModel):
    decision_id: str


class ReviewQueueGrantRequest(BaseModel):
    grant_id: str


class ReviewQueueCloseRequest(BaseModel):
    reason: str = ""


class ReviewQueueNeedsInformationRequest(BaseModel):
    reason: str = ""


class ReviewQueueCancelRequest(BaseModel):
    reason: str = ""


class ReviewQueueEscalateEntryRequest(BaseModel):
    reviewer: dict[str, Any] | None = None
    reason: str = ""
    actor_id: str | None = None


class KeyRegisterRequest(BaseModel):
    reviewer_id: str
    public_key_path: str


class KeyVerifyRegistryRequest(BaseModel):
    decision: dict[str, Any]


class AktaReviewRequest(BaseModel):
    akta_record: dict[str, Any]
    akta_trigger: dict[str, Any]
    grant_scope: str
    reviewer: dict[str, Any]
    decision_rationale: str
    out_dir: str | None = None
    signing_key_path: str | None = None
    signing_provider: str | None = None
    reviewer_id: str | None = None
    identity_token: str | None = None
    queue_dir: str | None = None
    session_mode: bool = False
    session_complete: bool = False
    votes: list[dict[str, Any]] | None = None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ScopeValidationError, GrantValidationError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@app.exception_handler(ScopeValidationError)
async def _scope_validation_handler(_request: Request, exc: ScopeValidationError) -> HTTPException:
    raise _http_error(exc)


@app.exception_handler(GrantValidationError)
async def _grant_validation_handler(_request: Request, exc: GrantValidationError) -> HTTPException:
    raise _http_error(exc)


@app.get("/v0/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/v0/packets", dependencies=[Depends(_require_api_key)])
def create_packet(req: PacketCreateRequest) -> dict[str, Any]:
    return get_engine().create_packet(req.akta_record, req.akta_trigger, vsa_report=req.vsa_report)


@app.post("/v0/packets/validate", dependencies=[Depends(_require_api_key)])
def validate_packet(packet: dict[str, Any]) -> dict[str, str]:
    get_engine().validate_packet(packet)
    return {"status": "valid"}


@app.post("/v0/packets/render", dependencies=[Depends(_require_api_key)])
def render_packet(req: PacketRenderRequest) -> dict[str, str]:
    engine = get_engine()
    content = (
        render_html(req.packet, engine.policy)
        if req.format == "html"
        else render_markdown(req.packet, engine.policy)
    )
    return {"format": req.format, "content": content}


@app.post("/v0/decisions", dependencies=[Depends(_require_api_key)])
def submit_decision(req: DecisionRequest) -> dict[str, Any]:
    try:
        return get_engine().submit_decision(req.packet, req.reviewer, req.decision)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/decisions/sign", dependencies=[Depends(_require_api_key)])
def sign_decision(req: SignRequest) -> dict[str, Any]:
    try:
        signer = _signer_from_env(req.key_path)
        return get_engine().sign_decision(req.artifact, signer)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/review-sessions", dependencies=[Depends(_require_api_key)])
def create_review_session(req: ReviewSessionCreateRequest) -> dict[str, Any]:
    session = get_engine().create_review_session(req.packet, quorum_policy=req.quorum_policy)
    return session.to_artifact()


@app.get("/v0/review-sessions/{session_id}", dependencies=[Depends(_require_api_key)])
def get_review_session(session_id: str) -> dict[str, Any]:
    try:
        return get_engine().session_status(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v0/review-sessions/{session_id}/votes", dependencies=[Depends(_require_api_key)])
def submit_review_vote(session_id: str, req: ReviewSessionVoteRequest) -> dict[str, Any]:
    try:
        session = get_engine().get_review_session(session_id, req.packet)
        decision = get_engine().submit_session_decision(
            session,
            req.packet,
            req.reviewer,
            req.decision,
            replace_vote=req.replace_vote,
        )
        return {"decision": decision, "session": session.to_artifact()}
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/review-sessions/{session_id}/grants", dependencies=[Depends(_require_api_key)])
def issue_grant_from_session(session_id: str, req: ReviewSessionGrantRequest) -> dict[str, Any]:
    try:
        session = get_engine().get_review_session(session_id, req.packet)
        return get_engine().issue_grant_from_session(session, req.packet, req.decisions)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/grants", dependencies=[Depends(_require_api_key)])
def issue_grant(req: GrantIssueRequest) -> dict[str, Any]:
    try:
        return get_engine().issue_grant(req.packet, req.decision)
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/grants/check", dependencies=[Depends(_require_api_key)])
def check_grant(req: GrantCheckRequest) -> dict[str, Any]:
    return get_engine().check_grant_detailed(req.grant, req.requested_tool, req.context)


@app.post("/v0/grants/revoke", dependencies=[Depends(_require_api_key)])
def revoke_grant(req: GrantRevokeRequest) -> dict[str, Any]:
    return get_engine().revoke_grant(
        req.grant_id,
        reason=req.reason,
        reviewer_withdrawal=req.reviewer_withdrawal,
    )


@app.get("/v0/grants/{grant_id}/status", dependencies=[Depends(_require_api_key)])
def grant_status(grant_id: str) -> dict[str, Any]:
    return get_engine().grant_status(grant_id)


@app.post("/v0/grants/sign", dependencies=[Depends(_require_api_key)])
def sign_grant(req: SignRequest) -> dict[str, Any]:
    try:
        signer = _signer_from_env(req.key_path)
        return get_engine().sign_grant(req.artifact, signer)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/verify", dependencies=[Depends(_require_api_key)])
def verify_artifact(req: VerifyRequest) -> dict[str, bool]:
    try:
        if req.public_key_path:
            verifier = Ed25519PublicVerifier(req.public_key_path)
        else:
            verifier = _signer_from_env(req.key_path)
        engine = get_engine()
        ok = (
            engine.verify_decision(req.artifact, verifier)
            if req.artifact_type == "decision"
            else engine.verify_grant(req.artifact, verifier)
        )
        return {"valid": ok}
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.get("/v0/quality", dependencies=[Depends(_require_api_key)])
def quality(queue_dir: str | None = None) -> dict[str, Any]:
    return get_engine().quality_report(queue_dir=queue_dir)


@app.post("/v0/akta/review", dependencies=[Depends(_require_api_key)])
def akta_review(req: AktaReviewRequest) -> dict[str, Any]:
    from scope.akta_review import run_akta_review

    try:
        out_dir = req.out_dir
        if not out_dir:
            out_dir = tempfile.mkdtemp(prefix="scope-akta-review-")
        summary = run_akta_review(
            get_engine(),
            akta_record=req.akta_record,
            akta_trigger=req.akta_trigger,
            grant_scope=req.grant_scope,
            reviewer=req.reviewer,
            decision_rationale=req.decision_rationale,
            out_dir=out_dir,
            signing_key=req.signing_key_path,
            signing_provider=req.signing_provider,
            reviewer_id=req.reviewer_id,
            identity_token=req.identity_token,
            queue_dir=req.queue_dir,
            session_mode=req.session_mode,
            session_complete=req.session_complete,
            votes=req.votes,
        )
        return summary
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/review-queue", dependencies=[Depends(_require_api_key)])
def create_review_queue(req: ReviewQueueCreateRequest) -> dict[str, Any]:
    engine = get_engine()
    entry = engine.create_review_queue(
        req.packet,
        queue_dir=req.queue_dir,
        sla_hours=req.sla_hours,
        auto_assign=req.auto_assign,
    )
    return entry.status_summary()


@app.get("/v0/review-queue", dependencies=[Depends(_require_api_key)])
def list_review_queue(queue_dir: str | None = None) -> dict[str, Any]:
    return get_engine().review_queue_status(queue_dir=queue_dir)


def _find_queue_path(queue_id: str, queue_dir: str | None = None) -> Path:
    from scope.errors import ScopeValidationError
    from scope.review_queue import ReviewQueue, list_queue_files

    engine = get_engine()
    try:
        effective = engine.effective_queue_dir(queue_dir)
    except ScopeValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    for path in list_queue_files(effective):
        entry = ReviewQueue.load(path)
        if entry.queue_id == queue_id:
            return path
    raise HTTPException(status_code=404, detail=f"Queue {queue_id} not found")


@app.post("/v0/review-queue/{queue_id}/assign", dependencies=[Depends(_require_api_key)])
def assign_review_queue(
    queue_id: str,
    req: ReviewQueueAssignRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().assign_review_queue(path, req.reviewer)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/decide", dependencies=[Depends(_require_api_key)])
def decide_review_queue(
    queue_id: str,
    req: ReviewQueueDecideRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().decide_review_queue(path, req.decision_id)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/grant", dependencies=[Depends(_require_api_key)])
def grant_review_queue(
    queue_id: str,
    req: ReviewQueueGrantRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().grant_review_queue(path, req.grant_id)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/close", dependencies=[Depends(_require_api_key)])
def close_review_queue(
    queue_id: str,
    req: ReviewQueueCloseRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().close_review_queue(path, reason=req.reason)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/in-review", dependencies=[Depends(_require_api_key)])
def in_review_review_queue(
    queue_id: str,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().in_review_review_queue(path)
    return ReviewQueue.load(path).status_summary()


@app.post(
    "/v0/review-queue/{queue_id}/needs-information",
    dependencies=[Depends(_require_api_key)],
)
def needs_information_review_queue(
    queue_id: str,
    req: ReviewQueueNeedsInformationRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().needs_information_review_queue(path, reason=req.reason)
    return ReviewQueue.load(path).status_summary()


@app.post(
    "/v0/review-queue/{queue_id}/information-received",
    dependencies=[Depends(_require_api_key)],
)
def information_received_review_queue(
    queue_id: str,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().information_received_review_queue(path)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/reopen", dependencies=[Depends(_require_api_key)])
def reopen_review_queue(
    queue_id: str,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().reopen_review_queue(path)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/expire", dependencies=[Depends(_require_api_key)])
def expire_review_queue(
    queue_id: str,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().expire_review_queue(path)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/cancel", dependencies=[Depends(_require_api_key)])
def cancel_review_queue(
    queue_id: str,
    req: ReviewQueueCancelRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().cancel_review_queue(path, reason=req.reason)
    return ReviewQueue.load(path).status_summary()


@app.post("/v0/review-queue/{queue_id}/escalate", dependencies=[Depends(_require_api_key)])
def escalate_review_queue_entry(
    queue_id: str,
    req: ReviewQueueEscalateEntryRequest,
    queue_dir: str | None = None,
) -> dict[str, Any]:
    from scope.review_queue import ReviewQueue

    path = _find_queue_path(queue_id, queue_dir)
    get_engine().escalate_review_queue_entry(
        path,
        req.reviewer,
        reason=req.reason,
        actor_id=req.actor_id,
    )
    return ReviewQueue.load(path).status_summary()


def _policy_dir() -> Path:
    return Path(get_engine().policy.policy_dir)


@app.get("/v0/keys", dependencies=[Depends(_require_api_key)])
def list_keys() -> dict[str, Any]:
    from scope.key_registry import verify_registry_integrity

    return verify_registry_integrity(_policy_dir())


@app.post("/v0/keys/register", dependencies=[Depends(_require_api_key)])
def register_key(req: KeyRegisterRequest) -> dict[str, Any]:
    from scope.key_registry import register_reviewer_key

    try:
        result = register_reviewer_key(
            _policy_dir(),
            req.reviewer_id,
            req.public_key_path,
        )
        global _engine
        _engine = None
        return result
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/keys/verify-registry", dependencies=[Depends(_require_api_key)])
def verify_key_registry(req: KeyVerifyRegistryRequest) -> dict[str, Any]:
    from scope.key_registry import verify_decision_against_registry

    try:
        return verify_decision_against_registry(req.decision, _policy_dir())
    except Exception as exc:
        raise _http_error(exc) from exc


@app.post("/v0/export/pf", dependencies=[Depends(_require_api_key)])
def export_pf(grant: dict[str, Any]) -> dict[str, Any]:
    from adapters.pf_core.export_obligation import export_pf_obligation

    return export_pf_obligation(grant)


@app.post("/v0/export/pf/validate", dependencies=[Depends(_require_api_key)])
def validate_pf_export_endpoint(body: dict[str, Any]) -> dict[str, str]:
    from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export

    grant = body["grant"]
    obligation = body.get("obligation") or export_pf_obligation(grant)
    schema = _SCHEMAS_DIR / "pf_scope_obligation.schema.json"
    validate_pf_export(obligation, grant, schema if schema.exists() else None)
    return {"status": "valid"}


@app.post("/v0/export/pcs", dependencies=[Depends(_require_api_key)])
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
        registry_version=engine.policy.reviewer_key_registry_version,
        registry_hash=engine.policy.reviewer_key_registry_hash,
    )
    if req.run_validation:
        schema = _SCHEMAS_DIR / "pcs_scope_artifact.schema.json"
        validate_pcs_export(tmp, schema if schema.exists() else None)
    return {"path": str(tmp), "validated": str(req.run_validation).lower()}


@app.post("/v0/export/pcs/validate", dependencies=[Depends(_require_api_key)])
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
        registry_version=engine.policy.reviewer_key_registry_version,
        registry_hash=engine.policy.reviewer_key_registry_hash,
    )
    schema = _SCHEMAS_DIR / "pcs_scope_artifact.schema.json"
    validate_pcs_export(tmp, schema if schema.exists() else None)
    return {"status": "valid", "path": str(tmp)}


@app.post("/v0/ledger/violations", dependencies=[Depends(_require_api_key)])
def record_ledger_violation(req: LedgerViolationRequest) -> dict[str, Any]:
    return get_engine().record_runtime_violation(
        req.grant_id, tool=req.tool, reason=req.reason
    )


@app.post("/v0/ledger/expiration", dependencies=[Depends(_require_api_key)])
def record_ledger_expiration(req: LedgerExpirationRequest) -> dict[str, Any]:
    return get_engine().record_grant_expiration(
        req.grant_id, reason=req.reason, packet_id=req.packet_id
    )


@app.post("/v0/identity/verify-token", dependencies=[Depends(_require_api_key)])
def verify_identity_token(req: IdentityVerifyRequest) -> dict[str, Any]:
    from scope.identity import verify_token_from_env

    identity = verify_token_from_env(req.token, policy_dir=_policy_dir())
    return {
        "reviewer_id": identity.reviewer_id,
        "role": identity.role,
    }


@app.post("/v0/review-queue/escalate", dependencies=[Depends(_require_api_key)])
def escalate_review_queue(
    queue_dir: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    return get_engine().escalate_review_queues(queue_dir=queue_dir, dry_run=dry_run)
