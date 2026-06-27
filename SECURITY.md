# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Report security issues privately to the repository maintainers via GitHub Security Advisories on [fraware/SCOPE](https://github.com/fraware/SCOPE).

## v0.1 security model

SCOPE v0.1 provides schema validation, canonical hashing, hash-chained ledger events, explicit expiration checks, and fail-closed behavior for unknown scopes and invalid roles. It does not provide digital signatures, identity provider integration, or tamper-evident external ledgers.

See [docs/threat_model.md](docs/threat_model.md) for details.
