"""SCOPE CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from scope import ScopeEngine
from scope.render import render_html, render_markdown
from scope.review_session import ReviewSession


def _load_json(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


def _write_json(path: str, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _engine(policy: str | None, ledger: str | None) -> ScopeEngine:
    return ScopeEngine.from_policy_dir(policy or "policy/", ledger_path=ledger)


@click.group()
def main() -> None:
    """Scoped Scientific Authorization Protocol CLI."""


@main.group("packet")
def packet_group() -> None:
    """SCOPE Packet operations."""


@packet_group.command("create")
@click.option("--akta-record", required=False, type=click.Path(exists=True), default=None)
@click.option("--akta-trigger", required=False, type=click.Path(exists=True), default=None)
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def packet_create(akta_record: str | None, akta_trigger: str | None, out: str, policy: str) -> None:
    if not akta_record and not akta_trigger:
        raise click.UsageError("At least one of --akta-record or --akta-trigger is required")
    engine = _engine(policy, None)
    pkt = engine.create_packet(akta_record, akta_trigger)
    _write_json(out, pkt)
    click.echo(f"Created packet {pkt['packet_id']} -> {out}")


@packet_group.command("validate")
@click.argument("packet_path", type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def packet_validate(packet_path: str, policy: str) -> None:
    engine = _engine(policy, None)
    pkt = _load_json(packet_path)
    engine.validate_packet(pkt)
    click.echo("Packet valid.")


@packet_group.command("render")
@click.argument("packet_path", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["markdown", "html"]), default="markdown")
@click.option("--out", type=click.Path(), default=None)
def packet_render(packet_path: str, fmt: str, out: str | None) -> None:
    pkt = _load_json(packet_path)
    content = render_html(pkt) if fmt == "html" else render_markdown(pkt)
    if out:
        Path(out).write_text(content, encoding="utf-8")
        click.echo(f"Rendered packet -> {out}")
    else:
        click.echo(content)


@main.group("decision")
def decision_group() -> None:
    """SCOPE Decision operations."""


@decision_group.command("submit")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--reviewer", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def decision_submit(packet: str, reviewer: str, decision: str, out: str, policy: str) -> None:
    engine = _engine(policy, None)
    result = engine.submit_decision(_load_json(packet), reviewer, _load_json(decision))
    _write_json(out, result)
    click.echo(f"Submitted decision {result['decision_id']} -> {out}")


@decision_group.command("sign")
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--key", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def decision_sign(decision: str, key: str, out: str) -> None:
    from scope.signing import Ed25519Signer

    dec = _load_json(decision)
    signer = Ed25519Signer(key)
    signed = ScopeEngine.from_policy_dir("policy/").sign_decision(dec, signer)
    _write_json(out, signed)
    click.echo(f"Signed decision -> {out}")


@main.group("grant")
def grant_group() -> None:
    """SCOPE Grant operations."""


@grant_group.command("issue")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def grant_issue(packet: str, decision: str, out: str, policy: str) -> None:
    engine = _engine(policy, None)
    grant = engine.issue_grant(_load_json(packet), _load_json(decision))
    _write_json(out, grant)
    click.echo(f"Issued grant {grant['grant_id']} -> {out}")


@grant_group.command("check")
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--requested-tool", required=True)
@click.option("--context", type=click.Path(exists=True), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(exists=True), default=None)
def grant_check(
    grant: str, requested_tool: str, context: str | None, policy: str, ledger: str | None
) -> None:
    engine = _engine(policy, ledger)
    ctx = _load_json(context) if context else {}
    ok = engine.check_grant(_load_json(grant), requested_tool, ctx)
    if ok:
        click.echo("ALLOWED")
        sys.exit(0)
    click.echo("BLOCKED")
    sys.exit(1)


@grant_group.command("revoke")
@click.option("--grant-id", required=True)
@click.option("--reason", default="Manual revocation")
@click.option("--ledger", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def grant_revoke(grant_id: str, reason: str, ledger: str, policy: str) -> None:
    engine = _engine(policy, ledger)
    event = engine.revoke_grant(grant_id, reason=reason)
    click.echo(f"Revoked grant {grant_id}: {event['event_id']}")


@grant_group.command("status")
@click.option("--grant-id", required=True)
@click.option("--ledger", required=True, type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def grant_status_cmd(grant_id: str, ledger: str, policy: str) -> None:
    engine = _engine(policy, ledger)
    status = engine.grant_status(grant_id)
    click.echo(json.dumps(status, indent=2))


@grant_group.command("sign")
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--key", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def grant_sign(grant: str, key: str, out: str) -> None:
    from scope.signing import Ed25519Signer

    g = _load_json(grant)
    signer = Ed25519Signer(key)
    signed = ScopeEngine.from_policy_dir("policy/").sign_grant(g, signer)
    _write_json(out, signed)
    click.echo(f"Signed grant -> {out}")


@main.command("verify")
@click.option("--artifact", required=True, type=click.Path(exists=True))
@click.option("--key", required=True, type=click.Path(exists=True))
@click.option("--type", "artifact_type", type=click.Choice(["decision", "grant"]), required=True)
def verify_cmd(artifact: str, key: str, artifact_type: str) -> None:
    from scope.signing import Ed25519Signer

    data = _load_json(artifact)
    signer = Ed25519Signer(key)
    engine = ScopeEngine.from_policy_dir("policy/")
    ok = (
        engine.verify_decision(data, signer)
        if artifact_type == "decision"
        else engine.verify_grant(data, signer)
    )
    if ok:
        click.echo("VALID")
        sys.exit(0)
    click.echo("INVALID")
    sys.exit(1)


@main.group("export")
def export_group() -> None:
    """Export adapters."""


@export_group.command("pf")
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--validate", is_flag=True, default=False)
def export_pf(grant: str, out: str, validate: bool) -> None:
    from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export

    g = _load_json(grant)
    data = export_pf_obligation(g)
    _write_json(out, data)
    if validate:
        schema = Path("schemas/pf_scope_obligation.schema.json")
        validate_pf_export(data, g, schema if schema.exists() else None)
        click.echo("PF export validated.")
    click.echo(f"PF-Core obligation -> {out}")


@export_group.command("pcs")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--validate", is_flag=True, default=False)
def export_pcs(packet: str, decision: str, grant: str, out: str, validate: bool) -> None:
    from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export

    export_pcs_artifact(_load_json(packet), _load_json(decision), _load_json(grant), out)
    if validate:
        schema = Path("schemas/pcs_scope_artifact.schema.json")
        validate_pcs_export(out, schema if schema.exists() else None)
        click.echo("PCS export validated.")
    click.echo(f"PCS artifact -> {out}")


@main.group("quality")
def quality_group() -> None:
    """Quality reporting."""


@quality_group.command("report")
@click.option("--ledger", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def quality_report(ledger: str, out: str, policy: str) -> None:
    engine = _engine(policy, ledger)
    report = engine.quality_report()
    _write_json(out, report)
    click.echo(f"Quality report -> {out}")


@main.group("review")
def review_group() -> None:
    """Multi-reviewer review sessions."""


@review_group.group("session")
def session_group() -> None:
    """Review session lifecycle."""


def _load_session(
    session_path: str, packet_path: str, policy: str
) -> tuple[ReviewSession, dict[str, Any]]:
    artifact = _load_json(session_path)
    packet = _load_json(packet_path)
    session = ReviewSession.from_artifact(artifact, packet, _engine(policy, None).policy)
    return session, artifact


@session_group.command("create")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--quorum-policy", type=click.Path(exists=True), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def session_create(
    packet: str, out: str, quorum_policy: str | None, policy: str, ledger: str | None
) -> None:
    engine = _engine(policy, ledger)
    pkt = _load_json(packet)
    quorum = _load_json(quorum_policy) if quorum_policy else None
    session = engine.create_review_session(pkt, quorum_policy=quorum)
    _write_json(out, session.to_artifact())
    click.echo(f"Created review session {session.session_id} -> {out}")


@session_group.command("vote")
@click.option("--session", "session_path", required=True, type=click.Path(exists=True))
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--reviewer", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def session_vote(
    session_path: str,
    packet: str,
    reviewer: str,
    decision: str,
    out: str,
    policy: str,
    ledger: str | None,
) -> None:
    engine = _engine(policy, ledger)
    session, _ = _load_session(session_path, packet, policy)
    result = engine.submit_session_decision(
        session,
        _load_json(packet),
        _load_json(reviewer),
        _load_json(decision),
    )
    _write_json(out, result)
    _write_json(session_path, session.to_artifact())
    click.echo(f"Recorded vote {result['decision_id']} -> {out}")


@session_group.command("issue-grant")
@click.option("--session", "session_path", required=True, type=click.Path(exists=True))
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option(
    "--decision",
    "decision_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
)
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def session_issue_grant(
    session_path: str,
    packet: str,
    decision_paths: tuple[str, ...],
    out: str,
    policy: str,
    ledger: str | None,
) -> None:
    engine = _engine(policy, ledger)
    session, _ = _load_session(session_path, packet, policy)
    decisions = [_load_json(path) for path in decision_paths]
    grant = engine.issue_grant_from_session(session, _load_json(packet), decisions)
    _write_json(out, grant)
    click.echo(f"Issued grant {grant['grant_id']} from session -> {out}")


@session_group.command("status")
@click.option("--session", "session_path", required=True, type=click.Path(exists=True))
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def session_status(session_path: str, packet: str, policy: str) -> None:
    session, _ = _load_session(session_path, packet, policy)
    click.echo(json.dumps(session.to_artifact(), indent=2))


if __name__ == "__main__":
    main()
