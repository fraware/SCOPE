# PF-Core Bridge

SCOPE grants export to PF-Core runtime obligations that specify permitted and blocked tools.

## Export

```bash
scope export pf --grant grant.json --out pf_obligation.json
```

## Obligation fields

- `permitted_tools` — tools runtime may invoke
- `blocked_tools` — tools that must remain blocked
- `approved_scope` — SCOPE approval scope
- `constraints` — protocol version, single-use flags
- `expiration` — invalidation triggers

PF-Core verifies that runtime traces respect these obligations. SCOPE defines permission; PF-Core verifies compliance.
