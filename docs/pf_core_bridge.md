# PF-Core Bridge

SCOPE grants export to PF-Core runtime obligations that specify permitted and blocked tools.

Contract version: `pf-core-v0.5`. Full field mapping: [external_integration_contracts.md](external_integration_contracts.md).

## Export

```bash
scope export pf --grant grant.json --out pf_obligation.json --validate
```

Optional live validation when a PF-Core checkout is configured:

```bash
export PF_CORE_REPO_PATH=/path/to/pf-core
scope export pf --grant grant.json --out pf_obligation.json --validate --live
```

Sample output shape: [adapters/pf_core/examples/pf_obligation.json](../adapters/pf_core/examples/pf_obligation.json) (regenerate with a live grant for current contract fields).

## Obligation fields

- `obligation_version` — `pf-core-v0.5`
- `permitted_tools` — tools runtime may invoke
- `blocked_tools` — tools that must remain blocked
- `approved_scope` — SCOPE approval scope
- `constraints` — protocol version, single-use flags
- `expiration` — invalidation triggers
- Signature fields — copied when present on signed grant

PF-Core verifies that runtime traces respect these obligations. SCOPE defines permission; PF-Core verifies compliance.

## Related documentation

- [pcs_export.md](pcs_export.md) — PCS bundle includes `pf_obligation.json`
- [akta_scope_demo.md](akta_scope_demo.md) — end-to-end export demo
