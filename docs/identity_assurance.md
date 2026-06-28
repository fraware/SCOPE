# Identity Assurance (IAL)

SCOPE v0.7 records identity assurance levels on every decision and grant provenance block.

## Levels

| Level | Meaning |
|-------|---------|
| IAL0 | Caller-supplied reviewer JSON only; not institutional authority |
| IAL1 | Valid local signature on decision; no OIDC verification |
| IAL2 | OIDC-verified identity without matching institutional directory role |
| IAL3 | OIDC plus institutional directory role from `org_rbac.yaml` |
| IAL4 | OIDC plus active delegation record with `delegation_id` |

## Provenance fields

```json
{
  "identity_assurance_level": "IAL2",
  "role_resolution_source": "org_rbac",
  "delegation_id": "ds1->ds2",
  "identity_provider": "https://idp.example.com",
  "identity_claim_hash": "sha256:..."
}
```

## Rules

- Caller-supplied JSON alone is IAL0 and must not be labeled institutional in render output or documentation.
- OIDC without RBAC role match cannot grant institutional authority (IAL2 without role authority).
- Delegated roles require `delegation_id` from an active `org_rbac` delegation record.
- Wire identity via `--identity-token` or `SCOPE_OIDC_ENABLED` with `--enforce-rbac` / `SCOPE_ENFORCE_RBAC`.

## Configuration

- `policy/identity_mapping.yaml` — claim to reviewer_id and role mapping
- `policy/org_rbac.yaml` — institutional directory roles and delegations
- `SCOPE_OIDC_JWKS_URL`, `SCOPE_OIDC_ISSUER`, `SCOPE_OIDC_AUDIENCE`, `SCOPE_OIDC_PUBLIC_KEY_PEM`

Schema: `schemas/identity_assurance.schema.json`
