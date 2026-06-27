"""Optional FastAPI REST server for SCOPE v0.1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from scope import ScopeEngine

app = FastAPI(title="SCOPE REST API", version="0.1.0")
_engine: ScopeEngine | None = None


def get_engine() -> ScopeEngine:
    global _engine
    if _engine is None:
        policy = Path(__file__).resolve().parents[2] / "policy"
        _engine = ScopeEngine.from_policy_dir(policy)
    return _engine


class PacketCreateRequest(BaseModel):
    akta_record: dict[str, Any]
    akta_trigger: dict[str, Any]


class DecisionRequest(BaseModel):
    packet: dict[str, Any]
    reviewer: dict[str, Any]
    decision: dict[str, Any]


class GrantIssueRequest(BaseModel):
    packet: dict[str, Any]
    decision: dict[str, Any]


class GrantCheckRequest(BaseModel):
    grant: dict[str, Any]
    requested_tool: str
    context: dict[str, Any] | None = None


@app.get("/v0/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/v0/packets")
def create_packet(req: PacketCreateRequest) -> dict[str, Any]:
    return get_engine().create_packet(req.akta_record, req.akta_trigger)


@app.post("/v0/packets/validate")
def validate_packet(packet: dict[str, Any]) -> dict[str, str]:
    get_engine().validate_packet(packet)
    return {"status": "valid"}


@app.post("/v0/decisions")
def submit_decision(req: DecisionRequest) -> dict[str, Any]:
    try:
        return get_engine().submit_decision(req.packet, req.reviewer, req.decision)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v0/grants")
def issue_grant(req: GrantIssueRequest) -> dict[str, Any]:
    try:
        return get_engine().issue_grant(req.packet, req.decision)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v0/grants/check")
def check_grant(req: GrantCheckRequest) -> dict[str, Any]:
    ok = get_engine().check_grant(req.grant, req.requested_tool, req.context)
    return {"allowed": ok}


@app.get("/v0/quality")
def quality() -> dict[str, Any]:
    return get_engine().quality_report()


@app.post("/v0/export/pf")
def export_pf(grant: dict[str, Any]) -> dict[str, Any]:
    from adapters.pf_core.export_obligation import export_pf_obligation

    return export_pf_obligation(grant)


@app.post("/v0/export/pcs")
def export_pcs(body: dict[str, Any]) -> dict[str, str]:
    import tempfile

    from adapters.pcs.export_artifact import export_pcs_artifact

    tmp = Path(tempfile.mkdtemp(prefix="scope_pcs_"))
    export_pcs_artifact(body["packet"], body["decision"], body["grant"], tmp)
    return {"path": str(tmp)}
