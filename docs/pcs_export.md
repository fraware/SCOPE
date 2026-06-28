# PCS Export

PCS packages SCOPE artifacts into release chains.

Manifest version: `pcs-v0.5`. Full field mapping: [external_integration_contracts.md](external_integration_contracts.md).

## Export

```bash
scope export pcs \
  --packet packet.json \
  --decision decision.json \
  --grant grant.json \
  --out dist/pcs_scope_artifact/ \
  --validate
```

Optional live validation:

```bash
export PCS_CORE_REPO_PATH=/path/to/pcs-core
scope export pcs --packet p.json --decision d.json --grant g.json \
  --out dist/pcs_scope_artifact/ --validate --live
```

Sample layout: [examples/institutional_pilot/](../examples/institutional_pilot/) (run export to generate a full bundle).

## Output layout

- `scope_packet.json`
- `scope_decision.json`
- `scope_grant.json`
- `pf_obligation.json`
- `release_manifest.json` (artifact hashes, trust root, registry metadata)

Manifest includes `scope_trust_root_hash`, `registry_version`, `registry_hash`, and optional signature fields from signed decisions.

All artifacts are schema-valid and canonically hashable for release verification.

## Related documentation

- [pf_core_bridge.md](pf_core_bridge.md) — PF obligation export
- [key_management.md](key_management.md) — registry and trust root workflow
