# Identity Assurance (IAL)

SCOPE v0.7 records identity assurance levels on every decision and grant provenance block.

## Levels

| Level | Alias | Meaning |
|-------|-------|---------|
| IAL0 | `caller_supplied` | Caller-supplied reviewer JSON only; not institutional authority |
| IAL1 | `local_signed_key` | Valid local signature on decision; no OIDC verification |
| IAL2 | `oidc_verified` | OIDC-verified identity without matching institutional directory role |
| IAL3 | `oidc_plus_rbac_role` | OIDC plus institutional directory role from `org_rbac.yaml` |
| IAL4 | `oidc_plus_rbac_plus_delegation` | OIDC plus active delegation record with `delegation_id` |

## Provenance fields

```json
{
  "identity_assurance_level": "IAL2",
  "identity_source": "oidc_jwt",
  "role_resolution_source": "oidc_verified",
  "delegation_id": "ds1->ds2",
  "identity_claim_hash": "sha256:..."
}
```

`role_resolution_source` values:

- `caller_supplied` — IAL0 caller JSON only
- `local_signed_key` — IAL1 signed decision without OIDC
- `oidc_verified` — IAL2 OIDC identity without org RBAC role match
- `org_rbac` — IAL3/IAL4 institutional role resolved from `org_rbac.yaml`

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
