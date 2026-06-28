# PCS export examples

Sample PCS release layout produced by `adapters/pcs/export_artifact.py`:

- `scope_packet.json`
- `scope_decision.json`
- `scope_grant.json`
- `pf_obligation.json`
- `release_manifest.json` (artifact hashes, trust root, registry metadata)

Manifest version: `pcs-v0.5`. See [docs/pcs_export.md](../../docs/pcs_export.md).

## Generate live output

Use artifacts from [examples/institutional_pilot/](../../examples/institutional_pilot/) or your own grant workflow:

```bash
scope export pcs \
  --packet examples/institutional_pilot/scope_packet.json \
  --decision examples/institutional_pilot/scope_decision.json \
  --grant examples/institutional_pilot/scope_grant.json \
  --out dist/pcs_scope_artifact/ \
  --validate
```

Optional live contract validation:

```bash
export PCS_CORE_REPO_PATH=/path/to/pcs-core
scope export pcs \
  --packet examples/institutional_pilot/scope_packet.json \
  --decision examples/institutional_pilot/scope_decision.json \
  --grant examples/institutional_pilot/scope_grant.json \
  --out dist/pcs_scope_artifact/ --validate --live
```

The manifest includes canonical `sha256:` hashes for each artifact file plus `scope_trust_root_hash` when policy and registry are configured.

Field mapping: [docs/external_integration_contracts.md](../../docs/external_integration_contracts.md).
