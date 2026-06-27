# PCS export examples

Sample PCS release layout produced by `adapters/pcs/export_artifact.py`:

- `scope_packet.json`
- `scope_decision.json`
- `scope_grant.json`
- `pf_obligation.json`
- `release_manifest.json` (artifact hashes and source IDs)

Generate live output:

```bash
scope export pcs \
  --packet /tmp/packet.json \
  --decision /tmp/decision.json \
  --grant /tmp/grant.json \
  --out dist/pcs_scope_artifact/
```

The manifest includes canonical `sha256:` hashes for each artifact file.
