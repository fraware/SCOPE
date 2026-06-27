"""SCOPE CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from scope import ScopeEngine


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
@click.option("--akta-record", required=True, type=click.Path(exists=True))
@click.option("--akta-trigger", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
@click.option("--policy", default="policy/", type=click.Path(exists=True))
def packet_create(akta_record: str, akta_trigger: str, out: str, policy: str) -> None:
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
def grant_check(grant: str, requested_tool: str, context: str | None, policy: str) -> None:
    engine = _engine(policy, None)
    ctx = _load_json(context) if context else {}
    ok = engine.check_grant(_load_json(grant), requested_tool, ctx)
    if ok:
        click.echo("ALLOWED")
        sys.exit(0)
    click.echo("BLOCKED")
    sys.exit(1)


@main.group("export")
def export_group() -> None:
    """Export adapters."""


@export_group.command("pf")
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def export_pf(grant: str, out: str) -> None:
    from adapters.pf_core.export_obligation import export_pf_obligation

    data = export_pf_obligation(_load_json(grant))
    _write_json(out, data)
    click.echo(f"PF-Core obligation -> {out}")


@export_group.command("pcs")
@click.option("--packet", required=True, type=click.Path(exists=True))
@click.option("--decision", required=True, type=click.Path(exists=True))
@click.option("--grant", required=True, type=click.Path(exists=True))
@click.option("--out", required=True, type=click.Path())
def export_pcs(packet: str, decision: str, grant: str, out: str) -> None:
    from adapters.pcs.export_artifact import export_pcs_artifact

    export_pcs_artifact(_load_json(packet), _load_json(decision), _load_json(grant), out)
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


if __name__ == "__main__":
    main()
