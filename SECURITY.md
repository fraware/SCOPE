# Security Policy

## Supported versions

| Version | Supported | Notes |
| ------- | --------- | ----- |
| 0.8.x   | Yes       | Current release line; security fixes backported here |
| 0.7.x   | Best effort | Prior institutional pilot line; upgrade to 0.8.x recommended |
| 0.6.x and earlier | No | Unsupported; no security patches |

Report issues against the latest **0.8.x** release on [main](https://github.com/fraware/SCOPE).

## Reporting a vulnerability

Report security issues privately via GitHub Security Advisories on [fraware/SCOPE](https://github.com/fraware/SCOPE/security/advisories/new). Do not open public issues for undisclosed vulnerabilities.

## v0.8 security model

SCOPE v0.8.x builds on schema validation, canonical hashing, hash-chained ledger events, explicit expiration checks, and fail-closed behavior for unknown scopes, invalid roles, and forbidden queue transitions.

**Cryptography and signing**

- Ed25519 signatures on decisions and grants when production signing is enabled (`SCOPE_PRODUCTION_MODE`, minimum signing assurance policy in `policy/minimum_signing_assurance.yaml`)
- Signing assurance levels (SAL0–SAL4) with registry key binding and reviewer public-key references; external HSM/KMS interface documented for SAL4 (`docs/signing_assurance.md`, `docs/key_management.md`)
- Combined `scope_trust_root_hash` ties policy and reviewer registry integrity into decision, grant, and PCS export provenance

**Identity**

- Identity assurance levels (IAL0–IAL4) with provenance on decisions and session grants (`scope/identity_assurance.py`, `docs/identity_assurance.md`)
- Optional OIDC/JWT verification (`SCOPE_OIDC_*`, `scope identity verify-token`) for institutional identity claims; org RBAC in `policy/org_rbac.yaml` is separate from SCOPE scope authority

**Ledger and delivery**

- Local hash-chained JSONL ledger with verification APIs
- Optional remote HTTP append sink (`SCOPE_LEDGER_REMOTE_URL`); delivery semantics `best_effort`, `at_least_once` (spool), and `fail_closed` for high-risk grant issuance when remote delivery is required
- Runtime violation and expiration events for PF feedback loops; remote sink is not a WORM or authoritative tamper-evident store

**AKTA review contract**

- Signed `summary.json` artifacts validated against split schemas for `completed` vs `session_required` (`scope-akta-review-v0.8.1`); consumers must branch on `summary.status`

**Known limits**

- No live SAML/SCIM directory sync; RBAC and identity mapping are file-based
- Reviewer judgment, domain safety, and physical lab safety are out of scope
- See [docs/threat_model.md](docs/threat_model.md), [docs/trusted_boundary.md](docs/trusted_boundary.md), and [docs/limitations.md](docs/limitations.md) for residual risk and deployment boundaries.