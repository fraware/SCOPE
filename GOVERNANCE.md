# Governance

SCOPE is maintained as an open reference implementation for the Scoped Scientific Authorization Protocol.

## Current release

- **Latest stable:** v1.0.0 (contract freeze)
- **Policy bundle:** `scope-core-v1.0`
- **AKTA adapter contract:** `scope-akta-review-v1.0`

See [docs/compatibility_matrix.md](docs/compatibility_matrix.md) for cross-repo version alignment.

## Decision making

- Protocol schema and policy changes require review against the design specification and threat model.
- Breaking changes require a **major semver bump** (v1.0+).
- Additive CLI flags and optional REST fields may ship in minor releases when schemas remain backward compatible.

## Roles

- **Maintainers** — merge contributions, cut releases, triage security advisories
- **Contributors** — propose changes via pull request
- **Integrators** — AKTA, PF-Core, PCS, VSA adapter authors

## Release policy

Semantic versioning from v0.1 onward.

| Milestone | Theme |
| --------- | ----- |
| v0.8.x | Session workflow, split AKTA summary contracts |
| v0.9.x | AKTA session-complete orchestration, ecosystem demo |
| v0.10.x | Production trust (IdP, KMS, RBAC sync, WORM ledger) |
| v0.11.x | Workflow product (webhooks, tickets, tenant isolation) |
| v1.0.x | Schema freeze, compatibility matrix, governance alignment |

### v1.0 freeze criteria

- AKTA review summary schemas stable; deprecation policy documented
- Compatibility matrix published for SCOPE × AKTA × PF × PCS × VSA
- Extended evals and pilot fixture verifier green on Python 3.10–3.12
- SECURITY.md and CONTRIBUTING.md reflect production checklist

## Breaking-change policy (AKTA contract)

- Summary schema field removals or type changes → major bump + migration guide
- New optional summary fields → minor bump
- CLI-only additive flags under existing contract → patch or minor with docs update

Migration guides: [docs/akta_review_contract.md](docs/akta_review_contract.md).

## Security advisories

Security fixes may be backported to supported minor lines per the [SECURITY.md](SECURITY.md) supported-versions table. Critical fixes on 0.8.x+ when feasible.
