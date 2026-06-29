# Security Policy

## Supported versions

| Version | Supported | Notes |
| ------- | --------- | ----- |
| 1.0.x   | Yes       | Current stable line; contract freeze |
| 0.11.x  | Yes       | Workflow release; security fixes backported when feasible |
| 0.10.x  | Best effort | Production trust line; upgrade to 1.0.x recommended |
| 0.9.x   | Best effort | Ecosystem demo line |
| 0.8.x   | Best effort | Prior release line |
| 0.7.x and earlier | No | Unsupported |

Report issues against the latest **1.0.x** release on [main](https://github.com/fraware/SCOPE).

## Reporting a vulnerability

Report security issues privately via GitHub Security Advisories on [fraware/SCOPE](https://github.com/fraware/SCOPE/security/advisories/new). Do not open public issues for undisclosed vulnerabilities.

## v1.0 security model

SCOPE v1.0 builds on schema validation, canonical hashing, hash-chained ledger events, explicit expiration checks, and fail-closed behavior for unknown scopes, invalid roles, and forbidden queue transitions.

**Cryptography and signing**

- Ed25519 signatures on decisions and grants when production signing is enabled
- Signing assurance levels (SAL0–SAL4) with KMS reference adapter (`--signing-provider kms`)
- Combined `scope_trust_root_hash` ties policy and reviewer registry integrity into PCS export provenance

**Identity**

- Identity assurance levels (IAL0–IAL4); production mode rejects IAL0 unless `SCOPE_ALLOW_DEV_IAL0`
- Pluggable OIDC and SAML providers (`scope/identity_providers.py`)
- SCIM/LDAP RBAC sync via `scope rbac sync`

**Ledger and delivery**

- Local hash-chained JSONL ledger with WORM and verified remote sink options
- Delivery modes: `best_effort`, `at_least_once`, `fail_closed`
- REST API audit logging to ledger

**AKTA review contract**

- Frozen at `scope-akta-review-v1.0`; consumers branch on `summary.status`

**Workflow**

- Tenant-isolated review queues via `X-Scope-Tenant-Id`
- Webhook notifications on SLA breach

**Known limits**

- SAML verification requires external sidecar or pre-verified assertions in reference adapter
- Email notifications require institutional SMTP wiring
- Reviewer judgment and physical lab safety remain out of scope

See [docs/threat_model.md](docs/threat_model.md), [docs/trusted_boundary.md](docs/trusted_boundary.md), [docs/compatibility_matrix.md](docs/compatibility_matrix.md), and [docs/limitations.md](docs/limitations.md).
