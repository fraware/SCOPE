# PCS Export

PCS packages SCOPE artifacts into release chains.

## Export

```bash
scope export pcs \
  --packet packet.json \
  --decision decision.json \
  --grant grant.json \
  --out dist/pcs_scope_artifact/
```

## Output layout

- `scope_packet.json`
- `scope_decision.json`
- `scope_grant.json`
- `pf_obligation.json`
- `release_manifest.json` (artifact hashes)

All artifacts are schema-valid and canonically hashable for release verification.
