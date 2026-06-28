# Changelog

## v0.4.0 (2026-06-28)

Comprehensive hardening release:

- All 28 quality metrics implemented with ledger-backed semantics and warnings
- AKTA import schema validation; session artifact schema validation on save/load
- Review assignment engine with `review_assigned`, `review_opened`, `artifact_viewed` ledger events
- Retired single-decision `co_reviewers`; multi-role actions require review sessions
- Enforced `requires_roles` on scopes (e.g. robot_queue_submission)
- A8/A9 role matrix corrected; domain overlay policy support (`policy/domain_overlays/`)
- Review route promotion to `requested_scope` when valid (configurable)
- Extended expiration: domain overlay, model version, tool registry, reviewer withdrawal, validation run completion
- Signing identity binding with optional `reviewer_key_registry.yaml`
- SessionStore schema validation, packet snapshots, vote supersession (`--replace-vote`)
- VSA ScientificReport adapter (`adapters/vsa/`)
- Version alignment: artifacts, PF-Core (`pf-core-v0.4`), PCS (`pcs-v0.4`)
- REST grant check returns `{allowed, reason, code}`; optional `SCOPE_API_KEY` bearer auth
- Render hardening: explicit error sections, policy-driven blocked-tool severity
- Expanded biosecurity_reviewer and clinical_reviewer scope permissions

## v0.3.0 (2026-06-28)

Production signing flow, defensive AKTA bridge, and pilot readiness:

- Decision submit allows unsigned artifacts in production mode; grant issue requires signed decision
- `scope decision validate --require-signature` for explicit signature enforcement
- AKTA `review_scope` stored as `review_route` without coercing into `requested_scope`
- SessionStore abstraction (memory, JSON file, SQLite) with CLI and REST persistence
- Ed25519PublicVerifier for public-key-only verification (`scope verify --public-key`)
- Enhanced packet rendering with scope semantics, permits/denies, checklist, and warnings
- Institutional pilot examples and guides; updated limitations and trusted boundary docs
- Policy bundle tagged `scope-core-v0.3`

## v0.2.0 (2026-06-27)

Enforceable scoped authorization and review quality layer:

- AKTA bridge: nested record format, import schemas, record/trigger/combined support
- First-class `requested_scope` with `scope_inference_source` and fail-closed overbreadth rules
- Ledger-backed grant use, revocation, expiration with structured reasons
- Optional Ed25519 signatures on decisions and grants; production mode enforcement
- Multi-reviewer sessions with quorum policies (require_all, require_any, n_of_m, safety veto)
- Reviewer and role quality analytics with extended quality report sections
- Hardened PF/PCS exports with manifest hash validation
- Packet render CLI (markdown/html) with non-certification language
- Full AKTA to SCOPE to PF to PCS integration demo and tests
- REST API v0.2 endpoints: review sessions, grant revoke/status, sign/verify, packet render, export validation
- CLI review session workflow and production mode documentation

## v0.1.0 (2026-06-27)

Initial reference implementation:

- SCOPE Packet, Decision, and Grant artifacts with canonical hashing
- Reviewer role taxonomy and role-to-action matrix
- Approval scope hierarchy with fail-closed validation
- Grant expiration and runtime enforcement checks
- Hash-chained JSONL ledger and quality warnings
- AKTA import, PF-Core obligation export, PCS artifact export
- CLI and optional FastAPI REST server
- Eight evaluation scenarios and comprehensive pytest suite
