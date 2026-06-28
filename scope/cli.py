"""SCOPE CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from scope import ScopeEngine, create_session_store
from scope.render import render_html, render_markdown
from scope.review_session import ReviewSession
from scope.session_store import SessionStore


def _load_json(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


def _write_json(path: str, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _engine(
    policy: str | None,
    ledger: str | None,
    session_store: SessionStore | None = None,
) -> ScopeEngine:
    return ScopeEngine.from_policy_dir(
        policy or "policy/",
        ledger_path=ledger,
        session_store=session_store,
    )


def _session_store_from_options(store_type: str, session_dir: str | None) -> SessionStore:
    return create_session_store(store_type, session_dir)


@click.group()
def main() -> None:
    """Scoped Scientific Authorization Protocol CLI."""


@main.group("packet")
def packet_group() -> None:
    """SCOPE Packet operations."""


@packet_group.command("create")
@click.option("--akta-record", required=False, type=click.Path(exists=True), default=None)
@click.option("--akta-trigger", required=False, type=click.Path(exists=True), default=None)
@click.option("--vsa-report", required=False, type=click.Path(exists=True), default=None)
@click.option(
    "--vsa-url",
    required=False,
    default=None,
    help="Fetch VSA report from URL (or use VSA_API_URL + report id in path).",
)
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def packet_create(
    akta_record: str | None,
    akta_trigger: str | None,
    vsa_report: str | None,
    vsa_url: str | None,
    out: str,
    policy: str,
) -> None:
    if not akta_record and not akta_trigger:
        raise click.UsageError("At least one of --akta-record or --akta-trigger is required")
    engine = _engine(policy, None)
    vsa = None
    if vsa_url:
        from adapters.vsa.fetch_report import fetch_vsa_report_from_file_or_url

        vsa = fetch_vsa_report_from_file_or_url(vsa_url)
    elif vsa_report:
        vsa = _load_json(vsa_report)
    pkt = engine.create_packet(akta_record, akta_trigger, vsa_report=vsa)
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
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def packet_render(packet_path: str, fmt: str, out: str | None, policy: str) -> None:
    from scope.policy import PolicyStore

    pkt = _load_json(packet_path)
    pol = PolicyStore.from_dir(policy)
    content = render_html(pkt, pol) if fmt == "html" else render_markdown(pkt, pol)
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
@click.option(
    "--draft",
    is_flag=True,
    default=False,
    help="Mark decision as draft (signature required before grant in production mode).",
)
@click.option("--identity-token", default=None, help="OIDC JWT bearer token for reviewer identity.")
@click.option("--enforce-rbac", is_flag=True, default=False, help="Enforce org RBAC on submit.")
def decision_submit(
    packet: str,
    reviewer: str,
    decision: str,
    out: str,
    policy: str,
    draft: bool,
    identity_token: str | None,
    enforce_rbac: bool,
) -> None:
    engine = _engine(policy, None)
    decision_data = _load_json(decision)
    if draft:
        decision_data["draft"] = True
    result = engine.submit_decision(
        _load_json(packet),
        reviewer,
        decision_data,
        identity_token=identity_token,
        enforce_rbac=enforce_rbac or None,
    )
    _write_json(out, result)
    click.echo(f"Submitted decision {result['decision_id']} -> {out}")
    if result.get("signature_required"):
        click.echo("Note: signature_required=true (sign before grant issue in production mode).")


@decision_group.command("validate")
@click.argument("decision_path", type=click.Path(exists=True))
@click.option("--require-signature", is_flag=True, default=False)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def decision_validate(decision_path: str, require_signature: bool, policy: str) -> None:
    engine = _engine(policy, None)
    dec = _load_json(decision_path)
    engine.validate_decision(dec, require_signature=require_signature)
    click.echo("Decision valid.")


@decision_group.command("sign")
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--key", required=False, type=click.Path(exists=True), default=None)
@click.option(
    "--signing-provider",
    type=click.Choice(["local", "env", "registry"]),
    default=None,
    help="Signing key provider (alternative to --key).",
)
@click.option("--reviewer-id", default=None, help="Required for registry signing provider.")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def decision_sign(
    decision: str,
    key: str | None,
    signing_provider: str | None,
    reviewer_id: str | None,
    policy: str,
    out: str,
) -> None:
    from scope.signing_providers import resolve_signing_provider

    dec = _load_json(decision)
    if signing_provider:
        provider = resolve_signing_provider(
            signing_provider,
            policy_dir=policy,
            key_path=key,
            reviewer_id=reviewer_id,
        )
        signer = provider.get_signer(reviewer_id=reviewer_id)
    elif key:
        from scope.signing import Ed25519Signer

        signer = Ed25519Signer(key)
    else:
        raise click.UsageError("Provide --key or --signing-provider")
    signed = ScopeEngine.from_policy_dir(policy).sign_decision(dec, signer)
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
@click.option("--type", "artifact_type", type=click.Choice(["decision", "grant"]), required=True)
@click.option("--key", type=click.Path(exists=True), default=None, help="Private key (dev signing)")
@click.option(
    "--public-key",
    type=click.Path(exists=True),
    default=None,
    help="Public key PEM for verification without private key",
)
def verify_cmd(
    artifact: str, artifact_type: str, key: str | None, public_key: str | None
) -> None:
    from scope.signing import Ed25519PublicVerifier, Ed25519Signer, Signer, Verifier

    if not key and not public_key:
        raise click.UsageError("Provide --public-key for verification or --key for dev signing")
    data = _load_json(artifact)
    engine = ScopeEngine.from_policy_dir("policy/")
    verifier: Signer | Verifier
    if public_key:
        verifier = Ed25519PublicVerifier(public_key)
    else:
        assert key is not None
        verifier = Ed25519Signer(key)
    ok = (
        engine.verify_decision(data, verifier)
        if artifact_type == "decision"
        else engine.verify_grant(data, verifier)
    )
    if ok:
        click.echo("VALID")
        sys.exit(0)
    click.echo("INVALID")
    sys.exit(1)


@main.group("akta")
def akta_group() -> None:
    """AKTA integration helpers."""


@akta_group.command("review")
@click.option("--akta-trigger", required=True, type=click.Path(exists=True))
@click.option("--akta-record", required=True, type=click.Path(exists=True))
@click.option("--grant-scope", required=True, help="Approval scope to grant.")
@click.option("--reviewer", required=True, type=click.Path(exists=True))
@click.option("--decision-rationale", required=True, help="Reviewer rationale for the decision.")
@click.option("--out-dir", required=True, type=click.Path())
@click.option(
    "--signing-key",
    type=click.Path(exists=True),
    default=None,
    help="Ed25519 private key PEM; required in production mode before grant issue.",
)
@click.option(
    "--signing-provider",
    type=click.Choice(["local", "env", "registry"]),
    default=None,
)
@click.option("--reviewer-id", default=None, help="Required for registry signing provider.")
@click.option("--queue-dir", type=click.Path(), default=None, help="Auto-create queue entry.")
@click.option("--identity-token", default=None)
@click.option(
    "--session",
    is_flag=True,
    default=False,
    help="Create review session when multi-role review is required.",
)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def akta_review(
    akta_trigger: str,
    akta_record: str,
    grant_scope: str,
    reviewer: str,
    decision_rationale: str,
    out_dir: str,
    signing_key: str | None,
    signing_provider: str | None,
    reviewer_id: str | None,
    queue_dir: str | None,
    identity_token: str | None,
    session: bool,
    policy: str,
    ledger: str | None,
) -> None:
    """Run AKTA review: packet, decision, grant, and summary in one step."""
    from scope.akta_review import run_akta_review

    engine = _engine(policy, ledger)
    summary = run_akta_review(
        engine,
        akta_record=akta_record,
        akta_trigger=akta_trigger,
        grant_scope=grant_scope,
        reviewer=reviewer,
        decision_rationale=decision_rationale,
        out_dir=out_dir,
        signing_key=signing_key,
        signing_provider=signing_provider,
        queue_dir=queue_dir,
        identity_token=identity_token,
        session_mode=session,
    )
    click.echo(
        f"AKTA review complete: grant {summary['grant_id']} "
        f"({summary['approved_scope']}) -> {out_dir}"
    )


@main.group("export")
def export_group() -> None:
    """Export adapters."""


@export_group.command("pf")
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--validate", is_flag=True, default=False)
@click.option(
    "--live",
    is_flag=True,
    default=False,
    help="Run PF-Core repo validator when configured.",
)
def export_pf(grant: str, out: str, validate: bool, live: bool) -> None:
    from adapters.pf_core.export_obligation import export_pf_obligation, validate_pf_export
    from scope.external_contracts import validate_pf_export_live

    g = _load_json(grant)
    data = export_pf_obligation(g)
    _write_json(out, data)
    if validate:
        schema = Path("schemas/pf_scope_obligation.schema.json")
        validate_pf_export(data, g, schema if schema.exists() else None)
        click.echo("PF export validated.")
    if live:
        ok, message = validate_pf_export_live(data, g)
        click.echo(message)
        if not ok and not message.startswith("Skipped:"):
            raise click.ClickException(message)
    click.echo(f"PF-Core obligation -> {out}")


@export_group.command("pcs")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--validate", is_flag=True, default=False)
@click.option(
    "--live",
    is_flag=True,
    default=False,
    help="Run PCS-Core repo validator when configured.",
)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def export_pcs(
    packet: str,
    decision: str,
    grant: str,
    out: str,
    validate: bool,
    live: bool,
    policy: str,
) -> None:
    from adapters.pcs.export_artifact import export_pcs_artifact, validate_pcs_export
    from scope.external_contracts import validate_pcs_export_live
    from scope.policy import PolicyStore

    pol = PolicyStore.from_dir(policy)
    export_pcs_artifact(
        _load_json(packet),
        _load_json(decision),
        _load_json(grant),
        out,
        registry_version=pol.reviewer_key_registry_version,
        registry_hash=pol.reviewer_key_registry_hash,
    )
    if validate:
        schema = Path("schemas/pcs_scope_artifact.schema.json")
        validate_pcs_export(out, schema if schema.exists() else None)
        click.echo("PCS export validated.")
    if live:
        ok, message = validate_pcs_export_live(out)
        click.echo(message)
        if not ok and not message.startswith("Skipped:"):
            raise click.ClickException(message)
    click.echo(f"PCS artifact -> {out}")


@main.group("quality")
def quality_group() -> None:
    """Quality reporting."""


@quality_group.command("report")
@click.option("--ledger", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option(
    "--queue-dir",
    type=click.Path(),
    default=None,
    help="Review queue directory (default: .scope/queues).",
)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def quality_report(ledger: str, out: str, queue_dir: str | None, policy: str) -> None:
    engine = _engine(policy, ledger)
    report = engine.quality_report(queue_dir=queue_dir)
    _write_json(out, report)
    click.echo(f"Quality report -> {out}")


@main.group("review")
def review_group() -> None:
    """Review lifecycle events and multi-reviewer sessions."""


@review_group.command("open")
@click.option("--packet-id", required=True, help="SCOPE packet ID to open for review.")
@click.option("--actor-id", default=None, help="Reviewer or system actor opening the review.")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def review_open(
    packet_id: str,
    actor_id: str | None,
    policy: str,
    ledger: str | None,
) -> None:
    """Record review_opened ledger event for a packet."""
    engine = _engine(policy, ledger)
    event = engine.open_review(packet_id, actor_id=actor_id)
    click.echo(json.dumps(event, indent=2))


@review_group.command("view-artifact")
@click.option("--packet-id", required=True, help="SCOPE packet ID.")
@click.option("--artifact", "artifact_name", required=True, help="Artifact name viewed.")
@click.option("--actor-id", default=None, help="Reviewer viewing the artifact.")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def review_view_artifact(
    packet_id: str,
    artifact_name: str,
    actor_id: str | None,
    policy: str,
    ledger: str | None,
) -> None:
    """Record artifact_viewed ledger event."""
    engine = _engine(policy, ledger)
    event = engine.record_artifact_viewed(packet_id, artifact_name, actor_id=actor_id)
    click.echo(json.dumps(event, indent=2))


@review_group.group("session")
def session_group() -> None:
    """Review session lifecycle."""


def _load_session(
    session_path: str | None,
    packet_path: str,
    policy: str,
    *,
    session_id: str | None = None,
    session_store: SessionStore | None = None,
) -> tuple[ReviewSession, dict[str, Any]]:
    packet = _load_json(packet_path)
    engine = _engine(policy, None, session_store=session_store)
    if session_id:
        session = engine.get_review_session(session_id, packet)
        artifact = session.to_artifact()
    elif session_path:
        artifact = _load_json(session_path)
        session = ReviewSession.from_artifact(artifact, packet, engine.policy)
    else:
        raise click.UsageError("Provide --session file or --session-id")
    return session, artifact


def _session_options(func):
    func = click.option(
        "--session-store",
        type=click.Choice(["memory", "json", "sqlite"]),
        default="memory",
        help="Session persistence backend.",
    )(func)
    func = click.option(
        "--session-dir",
        type=click.Path(),
        default=None,
        help="Directory (json) or file path (sqlite) for session store.",
    )(func)
    return func


@session_group.command("create")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--quorum-policy", type=click.Path(exists=True), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
@_session_options
def session_create(
    packet: str,
    out: str,
    quorum_policy: str | None,
    policy: str,
    ledger: str | None,
    session_store: str,
    session_dir: str | None,
) -> None:
    store = _session_store_from_options(session_store, session_dir)
    engine = _engine(policy, ledger, session_store=store)
    pkt = _load_json(packet)
    quorum = _load_json(quorum_policy) if quorum_policy else None
    session = engine.create_review_session(pkt, quorum_policy=quorum)
    _write_json(out, session.to_artifact())
    click.echo(f"Created review session {session.session_id} -> {out}")


@session_group.command("vote")
@click.option("--session", "session_path", required=False, type=click.Path(exists=True))
@click.option("--session-id", default=None, help="Load session from store by ID.")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--reviewer", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option(
    "--replace-vote",
    is_flag=True,
    default=False,
    help="Supersede prior vote from same reviewer.",
)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
@_session_options
def session_vote(
    session_path: str | None,
    session_id: str | None,
    packet: str,
    reviewer: str,
    decision: str,
    out: str,
    policy: str,
    ledger: str | None,
    session_store: str,
    session_dir: str | None,
    replace_vote: bool,
) -> None:
    store = _session_store_from_options(session_store, session_dir)
    engine = _engine(policy, ledger, session_store=store)
    session, _ = _load_session(
        session_path, packet, policy, session_id=session_id, session_store=store
    )
    result = engine.submit_session_decision(
        session,
        _load_json(packet),
        _load_json(reviewer),
        _load_json(decision),
        replace_vote=replace_vote,
    )
    _write_json(out, result)
    if session_path:
        _write_json(session_path, session.to_artifact())
    click.echo(f"Recorded vote {result['decision_id']} -> {out}")


@session_group.command("issue-grant")
@click.option("--session", "session_path", required=False, type=click.Path(exists=True))
@click.option("--session-id", default=None, help="Load session from store by ID.")
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
@_session_options
def session_issue_grant(
    session_path: str | None,
    session_id: str | None,
    packet: str,
    decision_paths: tuple[str, ...],
    out: str,
    policy: str,
    ledger: str | None,
    session_store: str,
    session_dir: str | None,
) -> None:
    store = _session_store_from_options(session_store, session_dir)
    engine = _engine(policy, ledger, session_store=store)
    session, _ = _load_session(
        session_path, packet, policy, session_id=session_id, session_store=store
    )
    decisions = [_load_json(path) for path in decision_paths]
    grant = engine.issue_grant_from_session(session, _load_json(packet), decisions)
    _write_json(out, grant)
    click.echo(f"Issued grant {grant['grant_id']} from session -> {out}")


@session_group.command("status")
@click.option("--session", "session_path", required=False, type=click.Path(exists=True))
@click.option("--session-id", default=None, help="Query session status by ID from store.")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@_session_options
def session_status(
    session_path: str | None,
    session_id: str | None,
    packet: str,
    policy: str,
    session_store: str,
    session_dir: str | None,
) -> None:
    store = _session_store_from_options(session_store, session_dir)
    if session_id:
        engine = _engine(policy, None, session_store=store)
        click.echo(json.dumps(engine.session_status(session_id), indent=2))
        return
    session, _ = _load_session(
        session_path, packet, policy, session_id=session_id, session_store=store
    )
    click.echo(json.dumps(session.to_artifact(), indent=2))


@session_group.command("replicate")
@click.option("--source", required=True, type=click.Path(exists=True))
@click.option("--dest", required=True, type=click.Path())
def session_replicate(source: str, dest: str) -> None:
    from scope.session_store import replicate_sessions

    result = replicate_sessions(source, dest)
    click.echo(json.dumps(result, indent=2))


@review_group.group("queue")
def queue_group() -> None:
    """Review queue tracking (open, assigned, overdue)."""


@queue_group.command("create")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--queue-dir", type=click.Path(), default=None, help="Directory for queue artifacts.")
@click.option("--sla-hours", default=72, show_default=True, type=int)
@click.option(
    "--auto-assign",
    is_flag=True,
    default=False,
    help="Auto-assign first eligible reviewer from policy.",
)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def review_queue_create(
    packet: str,
    out: str,
    queue_dir: str | None,
    sla_hours: int,
    auto_assign: bool,
    policy: str,
) -> None:
    engine = _engine(policy, None)
    entry = engine.create_review_queue(
        _load_json(packet),
        queue_dir=queue_dir,
        sla_hours=sla_hours,
        auto_assign=auto_assign,
    )
    path = entry.save(out)
    click.echo(f"Created review queue {entry.queue_id} -> {path}")


@queue_group.command("assign")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--reviewer", required=True, type=click.Path(exists=True))
def review_queue_assign(queue_path: str, reviewer: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.assign(_load_json(reviewer))
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("list")
@click.option("--queue-dir", type=click.Path(), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def review_queue_list(queue_dir: str | None, policy: str) -> None:
    engine = _engine(policy, None)
    click.echo(json.dumps(engine.review_queue_status(queue_dir=queue_dir), indent=2))


@queue_group.command("in-review")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
def review_queue_in_review(queue_path: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.mark_in_review()
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("needs-information")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--reason", default="")
def review_queue_needs_information(queue_path: str, reason: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.mark_needs_information(reason=reason)
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("information-received")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
def review_queue_information_received(queue_path: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.mark_information_received()
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("reopen")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
def review_queue_reopen(queue_path: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.reopen()
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("expire")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
def review_queue_expire(queue_path: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.expire()
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("escalate-entry")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--reviewer", type=click.Path(exists=True), default=None)
@click.option("--reason", default="", help="Escalation reason recorded in queue artifact.")
@click.option("--actor-id", default=None, help="Actor performing the escalation.")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def review_queue_escalate_entry(
    queue_path: str,
    reviewer: str | None,
    reason: str,
    actor_id: str | None,
    policy: str,
    ledger: str | None,
) -> None:
    engine = _engine(policy, ledger)
    escalation = _load_json(reviewer) if reviewer else None
    entry = engine.escalate_review_queue_entry(
        queue_path,
        escalation,
        reason=reason,
        actor_id=actor_id,
    )
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("decide")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--decision-id", required=True)
def review_queue_decide(queue_path: str, decision_id: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.mark_decided(decision_id)
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("grant")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--grant-id", required=True)
def review_queue_grant(queue_path: str, grant_id: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.mark_granted(grant_id)
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("cancel")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--reason", default="")
def review_queue_cancel(queue_path: str, reason: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.cancel(reason=reason)
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("close")
@click.option("--queue", "queue_path", required=True, type=click.Path(exists=True))
@click.option("--reason", default="")
def review_queue_close(queue_path: str, reason: str) -> None:
    from scope.review_queue import ReviewQueue

    entry = ReviewQueue.load(queue_path)
    entry.close(reason=reason)
    entry.save(queue_path)
    click.echo(json.dumps(entry.status_summary(), indent=2))


@queue_group.command("status")
@click.option("--queue", "queue_path", required=False, type=click.Path(exists=True))
@click.option("--queue-dir", type=click.Path(), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def review_queue_status(
    queue_path: str | None,
    queue_dir: str | None,
    policy: str,
) -> None:
    if queue_path:
        from scope.review_queue import ReviewQueue

        click.echo(json.dumps(ReviewQueue.load(queue_path).status_summary(), indent=2))
        return
    engine = _engine(policy, None)
    click.echo(json.dumps(engine.review_queue_status(queue_dir=queue_dir), indent=2))


@queue_group.command("escalate")
@click.option("--queue-dir", type=click.Path(), default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
@click.option("--ledger", type=click.Path(), default=None)
def review_queue_escalate(
    queue_dir: str | None,
    dry_run: bool,
    policy: str,
    ledger: str | None,
) -> None:
    engine = _engine(policy, ledger)
    results = engine.escalate_review_queues(queue_dir=queue_dir, dry_run=dry_run)
    click.echo(json.dumps(results, indent=2))


@queue_group.command("dashboard")
@click.option("--out", required=True, type=click.Path())
@click.option("--queue-dir", type=click.Path(), default=None)
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def review_queue_dashboard_cmd(out: str, queue_dir: str | None, policy: str) -> None:
    from scope.review_queue_render import write_queue_dashboard

    path = write_queue_dashboard(out, queue_dir)
    click.echo(f"Queue dashboard -> {path}")


@main.group("ledger")
def ledger_group() -> None:
    """Ledger event recording."""


@ledger_group.command("record-violation")
@click.option("--grant-id", required=True)
@click.option("--tool", required=True)
@click.option("--reason", required=True)
@click.option("--ledger", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def ledger_record_violation(
    grant_id: str, tool: str, reason: str, ledger: str, policy: str
) -> None:
    engine = _engine(policy, ledger)
    event = engine.record_runtime_violation(grant_id, tool=tool, reason=reason)
    click.echo(json.dumps(event, indent=2))


@ledger_group.command("record-expiration")
@click.option("--grant-id", required=True)
@click.option(
    "--reason",
    required=True,
    type=click.Choice(
        [
            "protocol_version_change",
            "evidence_downgrade",
            "policy_version_change",
            "reviewer_withdrawal",
            "manual",
        ]
    ),
)
@click.option("--packet-id", default=None)
@click.option("--ledger", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def ledger_record_expiration(
    grant_id: str,
    reason: str,
    packet_id: str | None,
    ledger: str,
    policy: str,
) -> None:
    engine = _engine(policy, ledger)
    event = engine.record_grant_expiration(grant_id, reason=reason, packet_id=packet_id)
    click.echo(json.dumps(event, indent=2))


@main.group("identity")
def identity_group() -> None:
    """Institutional identity verification."""


@identity_group.command("verify-token")
@click.option("--token", required=True, help="JWT bearer token.")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def identity_verify_token(token: str, policy: str) -> None:
    import os

    from scope.identity import map_claims_to_reviewer, verify_jwt_token

    claims = verify_jwt_token(
        token,
        jwks_url=os.environ.get("SCOPE_OIDC_JWKS_URL"),
        issuer=os.environ.get("SCOPE_OIDC_ISSUER"),
        audience=os.environ.get("SCOPE_OIDC_AUDIENCE"),
        public_key_pem=os.environ.get("SCOPE_OIDC_PUBLIC_KEY_PEM"),
    )
    identity = map_claims_to_reviewer(claims, policy_dir=policy)
    click.echo(
        json.dumps(
            {
                "reviewer_id": identity.reviewer_id,
                "role": identity.role,
                "claims": identity.claims,
            },
            indent=2,
        )
    )


@main.group("policy")
def policy_group() -> None:
    """Policy bundle utilities."""


@policy_group.group("overlay")
def policy_overlay_group() -> None:
    """Domain overlay management."""


@policy_overlay_group.command("validate")
@click.option("--overlay", required=True, type=click.Path(exists=True))
def policy_overlay_validate(overlay: str) -> None:
    from scope.overlay import validate_overlay_file

    click.echo(json.dumps(validate_overlay_file(overlay), indent=2))


@policy_overlay_group.command("list")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def policy_overlay_list(policy: str) -> None:
    from scope.overlay import list_overlays

    click.echo(json.dumps(list_overlays(policy), indent=2))


@main.group("key")
def key_group() -> None:
    """Reviewer public key registry workflow."""


@key_group.command("list")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def key_list(policy: str) -> None:
    from scope.key_registry import verify_registry_integrity

    click.echo(json.dumps(verify_registry_integrity(policy), indent=2))


@key_group.command("register")
@click.option("--reviewer-id", required=True)
@click.option("--public-key", required=True, type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def key_register(
    reviewer_id: str,
    public_key: str,
    policy: str,
) -> None:
    from scope.key_registry import register_reviewer_key

    result = register_reviewer_key(
        policy,
        reviewer_id,
        public_key,
    )
    click.echo(json.dumps(result, indent=2))


@key_group.command("migrate-registry")
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def key_migrate_registry(policy: str) -> None:
    """Remove legacy private key fields from reviewer_key_registry.yaml."""
    from scope.key_registry import migrate_reviewer_registry

    result = migrate_reviewer_registry(policy)
    click.echo(json.dumps(result, indent=2))


@key_group.command("verify-registry")
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def key_verify_registry(decision: str, policy: str) -> None:
    from scope.key_registry import verify_decision_against_registry

    result = verify_decision_against_registry(_load_json(decision), policy)
    click.echo(json.dumps(result, indent=2))
    if result.get("signature_valid") is False:
        raise click.ClickException("Decision signature invalid against registry public key")


if __name__ == "__main__":
    main()
