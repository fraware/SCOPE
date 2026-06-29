# Compatibility Matrix (v1.0)

Published version alignment for SCOPE and partner integrations at v1.0.0.

## Core versions

| Component | Version constant | Notes |
|-----------|------------------|-------|
| SCOPE package | `0.11.0` → `1.0.0` | Semver from `scope/_version.py` |
| Policy bundle | `scope-core-v1.0` | YAML `version` field |
| AKTA review contract | `scope-akta-review-v1.0` | Branch on `summary.status` |
| PF obligation | `pf-core-v0.5` | `obligation_version` |
| PCS manifest | `pcs-v0.5` | `manifest_version` |
| VSA report import | adapter-local | No semver field; schema-stable fields documented |

## Cross-repo compatibility

| SCOPE | AKTA | PF-Core | PCS | VSA |
|-------|------|---------|-----|-----|
| 1.0.x | ≥ 0.4 trigger aliases | pf-core-v0.5 | pcs-v0.5 | ScientificReport v1 |
| 0.11.x | scope-akta-review-v0.9+ | pf-core-v0.5 | pcs-v0.5 | ScientificReport v1 |
| 0.10.x | scope-akta-review-v0.9+ | pf-core-v0.5 | pcs-v0.5 | ScientificReport v1 |
| 0.9.x | scope-akta-review-v0.9 | pf-core-v0.4–v0.5 | pcs-v0.4–v0.5 | ScientificReport v1 |
| 0.8.x | scope-akta-review-v0.8.1 | pf-core-v0.5 | pcs-v0.5 | ScientificReport v1 |

## Schema stability (v1.0 freeze)

Stable fields in `schemas/` will not be removed or change type without a major SCOPE bump. Deprecated fields remain readable for one major release with documented migration paths.

| Schema | Stable since |
|--------|--------------|
| `scope_akta_review_summary.schema.json` | v1.0.0 |
| `scope_akta_review_session_summary.schema.json` | v1.0.0 |
| `pf_scope_obligation.schema.json` | v0.7.0 |
| `pcs_scope_artifact.schema.json` | v0.7.0 |
| `scope_review_queue.schema.json` | v0.7.0 |

## Migration guides

- **v0.8 → v0.9:** Session-complete AKTA path; contract version bump to `scope-akta-review-v0.9`
- **v0.9 → v0.10:** Production IAL0 rejection; KMS signing provider; RBAC SCIM sync
- **v0.10 → v0.11:** Tenant queue isolation; webhook notifications; REST audit logging
- **v0.11 → v1.0:** Contract freeze at `scope-akta-review-v1.0`; no breaking schema changes

See [akta_review_contract.md](akta_review_contract.md), [external_integration_contracts.md](external_integration_contracts.md).
