# Security Policy

## Supported versions

| Version | Supported | Notes |
| ------- | --------- | ----- |
| 1.0.x   | Yes       | Stable contract; security advisories for 1.0.x |
| 0.11.x  | Yes       | Workflow release; migrate to 1.0 for contract freeze |
| 0.10.x  | Yes       | Production-trust adapters |
| 0.9.x   | Yes       | AKTA session-complete integration |
| 0.8.x   | Yes       | Split AKTA summary contracts, pilot fixtures |
| 0.7.x   | Limited   | Critical fixes only |
| < 0.7   | No        | Upgrade required |

## Reporting a vulnerability

Report security issues privately to the repository maintainers via GitHub Security Advisories on [fraware/SCOPE](https://github.com/fraware/SCOPE).

Include: affected version, reproduction steps, impact assessment, and suggested fix if available.

## Security model (v0.8+)

SCOPE provides layered institutional trust boundaries:

- **Identity assurance (IAL0–IAL4)**: OIDC/JWT verification, optional SAML assertion verify, org RBAC mapping. Production mode rejects caller-supplied identity JSON without verified tokens (`SCOPE_PRODUCTION_MODE=1`).
- **Signing assurance (SAL0–SAL4)**: Ed25519 local keys, registry-backed keys, and reference KMS/HSM adapters. Minimum SAL enforced per scope in `policy/minimum_signing_assurance.yaml`.
- **Authority provenance**: Two-stage RBAC + SCOPE authority checks with explicit `authority_checks` on decisions and grants.
- **Ledger integrity**: Hash-chained local JSONL, optional remote/WORM sinks with `fail_closed` delivery for high-risk events.
- **AKTA contract**: Split summary schemas (`completed` vs `session_required`); verifiable pilot fixture pack.

SCOPE does **not** replace IRB, biosafety, EHS, or certify scientific safety. See [docs/limitations.md](docs/limitations.md).

## Cryptography

- Decision and grant signatures use **Ed25519** (local PEM or registry-backed keys).
- OIDC tokens verified via JWKS (RS256) or static public key.
- Ledger events use SHA-256 hash chaining.

## Operational hardening

For production deployment guidance see [docs/production_deployment.md](docs/production_deployment.md) and [docs/trusted_boundary.md](docs/trusted_boundary.md).

Threat model details: [docs/threat_model.md](docs/threat_model.md).
