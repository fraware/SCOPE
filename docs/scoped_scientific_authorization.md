# Scoped Scientific Authorization

SCOPE (v0.7.0) turns AKTA `review_required` and `authorization_required` outputs into structured scientific review packets, typed reviewer assignments, scoped decisions, expiring grants, runtime obligations, and audit-ready records.

## Core doctrine

Review is a role, artifact, scope, expiration, and accountability trail.

See [review_doctrine.md](review_doctrine.md) and [field_thesis.md](field_thesis.md).

## Artifacts

1. **SCOPE Packet** — artifacts a reviewer must inspect
2. **SCOPE Decision** — structured reviewer response with identity and authority provenance
3. **SCOPE Grant** — machine-readable authorization for runtime with signing assurance
4. **SCOPE Ledger** — hash-chained audit trail with configurable delivery modes
5. **SCOPE Quality Report** — review quality metrics and warnings

## Assurance models (v0.7)

| Model | Levels | Purpose |
|-------|--------|---------|
| Identity assurance (IAL) | IAL0–IAL4 | How reviewer identity was established |
| Signing assurance (SAL) | SAL0–SAL4 | How decisions and grants were signed |
| Authority checks | Two-stage | Org RBAC then SCOPE scope policy separation |

Details: [identity_assurance.md](identity_assurance.md), [signing_assurance.md](signing_assurance.md), [rbac_scope_authority.md](rbac_scope_authority.md).

## Ecosystem role

- **AKTA** classifies scientific action admissibility
- **SCOPE** reviews and authorizes within scope
- **PF-Core** verifies runtime compliance (`pf-core-v0.5` obligations)
- **PCS** packages release artifacts (`pcs-v0.5` manifests)

Primary AKTA path: `scope akta review` — see [akta_review_contract.md](akta_review_contract.md).

## Documentation index

| Topic | Document |
|-------|----------|
| Pilot onboarding | [institutional_pilot_guide.md](institutional_pilot_guide.md) |
| Trust assumptions | [trusted_boundary.md](trusted_boundary.md) |
| Limitations | [limitations.md](limitations.md) |
| Integration contracts | [external_integration_contracts.md](external_integration_contracts.md) |
| Reviewer guidance | [reviewer_guide.md](reviewer_guide.md) |
| Threat model | [threat_model.md](threat_model.md) |
