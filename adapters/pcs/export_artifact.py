"""Export PCS-compatible release artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.pf_core.export_obligation import export_pf_obligation
from scope.hash import compute_hash


def export_pcs_artifact(
    packet: dict[str, Any],
    decision: dict[str, Any],
    grant: dict[str, Any],
    out_dir: str | Path,
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

    manifest = {
        "manifest_version": "pcs-v0.1",
        "artifacts": list(artifacts.keys()),
        "hashes": {name: compute_hash(data) for name, data in artifacts.items()},
        "source": {
            "akta_record_id": packet["source"]["akta_record_id"],
            "packet_id": packet["packet_id"],
            "decision_id": decision["decision_id"],
            "grant_id": grant["grant_id"],
        },
    }
    with (out / "release_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return out
