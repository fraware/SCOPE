"""Export PCS-compatible release artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from adapters.pf_core.export_obligation import export_pf_obligation
from scope.hash import compute_hash, verify_hash


def export_pcs_artifact(
    packet: dict[str, Any],
    decision: dict[str, Any],
    grant: dict[str, Any],
    out_dir: str | Path,
    *,
    ledger_events: list[dict[str, Any]] | None = None,
    quality_warnings: list[dict[str, str]] | None = None,
    registry_version: str | None = None,
    registry_hash: str | None = None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pf = export_pf_obligation(grant)
    artifacts = {
        "scope_packet.json": packet,
        "scope_decision.json": decision,
        "scope_grant.json": grant,
        "pf_obligation.json": pf,
    }
    for name, data in artifacts.items():
        with (out / name).open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")

    manifest: dict[str, Any] = {
        "manifest_version": "pcs-v0.4",
        "artifacts": list(artifacts.keys()),
        "hashes": {name: compute_hash(data) for name, data in artifacts.items()},
        "source": {
            "akta_record_id": packet["source"]["akta_record_id"],
            "packet_id": packet["packet_id"],
            "decision_id": decision["decision_id"],
            "grant_id": grant["grant_id"],
        },
    }
    if ledger_events:
        manifest["ledger_excerpt"] = ledger_events
    if quality_warnings:
        manifest["quality_warnings"] = quality_warnings
    for field in ("decision_signature", "grant_signature"):
        if decision.get(field):
            manifest["decision_signature"] = decision[field]
        if grant.get(field):
            manifest["grant_signature"] = grant[field]
    for field in ("reviewer_public_key_ref", "signature_algorithm", "signed_payload_hash"):
        if decision.get(field):
            manifest[field] = decision[field]
        elif grant.get(field):
            manifest[field] = grant[field]
    if registry_version:
        manifest["registry_version"] = registry_version
    if registry_hash:
        manifest["registry_hash"] = registry_hash

    with (out / "release_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return out


def validate_pcs_export(
    out_dir: str | Path,
    schema_path: str | Path | None = None,
) -> None:
    out = Path(out_dir)
    manifest_path = out / "release_manifest.json"
    if not manifest_path.exists():
        raise ValueError("Missing release_manifest.json")

    with manifest_path.open(encoding="utf-8") as fh:
        manifest = json.load(fh)

    for name in manifest.get("artifacts", []):
        path = out / name
        if not path.exists():
            raise ValueError(f"Missing artifact file: {name}")
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        expected = manifest.get("hashes", {}).get(name)
        actual = compute_hash(data)
        if expected != actual:
            raise ValueError(f"Hash mismatch for {name}: possible tampering")

    grant_path = out / "scope_grant.json"
    if grant_path.exists():
        with grant_path.open(encoding="utf-8") as fh:
            grant = json.load(fh)
        if not verify_hash(grant, "grant_hash"):
            raise ValueError("Grant hash invalid: possible tampering")

    if schema_path:
        with Path(schema_path).open(encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(instance=manifest, schema=schema)
