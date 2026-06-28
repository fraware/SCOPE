# Changelog

## v0.7.0 (2026-06-28)

Institutional pilot hardening release:

- **Identity assurance (IAL0–IAL4)**: `scope/identity_assurance.py`, provenance on decisions/grants (including session grants), OIDC + org RBAC wiring
- **RBAC vs SCOPE authority separation**: two-stage checks in `scope/authority.py` before decision acceptance
- **Ledger delivery semantics**: `best_effort`, `at_least_once`, `fail_closed` modes with spool, `delivery_state`, and fail-closed blocking on high-risk grant issuance
- **Review queue state machine**: explicit transitions (`in_review`, `needs_information`, `escalated`, `expired`, reopen)
- **Signing assurance (SAL0–SAL4)**: minimum policy, production enforcement, HSM/KMS external interface
- **Frozen AKTA review contract**: `summary.json` schema, `scope-akta-review-v0.7` adapter version
- Policy bundle tagged `scope-core-v0.7`

## v0.6.0 (2026-06-28)

Institutional foundations release:

- **OIDC/JWT identity**: `scope identity verify-token`, `SCOPE_OIDC_*` env vars, `--identity-token` on decision submit and akta review
- **Signing providers**: `LocalPemProvider`, `EnvKeyProvider`, `RegistryKeyProvider` via `--signing-provider`
- **Institutional RBAC**: `policy/org_rbac.yaml`, `scope/rbac.py`, `--enforce-rbac` / `SCOPE_ENFORCE_RBAC`
- **Review queue**: auto-assign, SLA escalation, file locking, static HTML dashboard
- **Ledger sinks**: local JSONL + optional `RemoteHttpSink` (`SCOPE_LEDGER_REMOTE_URL`)
- **Session HA hooks**: `ReplicatedJsonSessionStore`, `DistributedSessionStore`, `scope session replicate`
- **Runtime violation loop**: `scope ledger record-violation`, `POST /v0/ledger/violations`, quality metric
- **VSA live fetch**: `adapters/vsa/fetch_report.py`, `--vsa-url` on packet create
- **AKTA pipeline scripts**: `scripts/akta_scope_pipeline.ps1` / `.sh`
- **PF/PCS v0.5 contracts**: `pf-core-v0.5`, `pcs-v0.5` (backward compatible with v0.4 validators)
- **Domain overlays**: clinical research overlay, overlay CLI validate/list, biosecurity mandatory session
- **REST multi-tenant**: `EngineFactory` with `X-Scope-Policy-Dir`, `X-Scope-Ledger-Path` headers
- **AKTA review**: queue auto-create, `review_opened` ledger events, multi-role session detection

## v0.5.1 (2026-06-28)

Engineering review release:

- **`scope akta review`**: one-shot AKTA packet → decision → grant workflow with `summary.json`
- **Quality report `--queue-dir`**: wire queue metrics through CLI (default `.scope/queues`)
- **`scope key migrate-registry`**: strip legacy private key fields from registry YAML
- **`scope_trust_root_hash`**: combined SHA-256 of policy hash + registry hash in decision/grant provenance and PCS manifest
- **`POST /v0/akta/review`**: REST equivalent of `scope akta review`
- **`GET /v0/quality?queue_dir=`**: custom queue directory for quality metrics
- Production signing for `scope akta review` via `--signing-key`

## v0.5.0 (2026-06-28)

Integration and lab-workflow release:

- AKTA v0.4 trigger extraction: `admissibility`, `review_route`, nested and top-level constraints
- Expanded evidence vocabulary with AKTA↔SCOPE alias documentation and weak-evidence warnings
- Minimal review queue (`scope review queue create|assign|status`) persisted under `.scope/queues/`
- Quality report metrics: `open_queue_count`, `overdue_queue_count`
- Reviewer key registry CLI (`scope key register`, `scope key verify-registry`) with signing enforcement
- PCS export includes `reviewer_public_key_ref`, `registry_version`, `registry_hash`
- Optional live PF/PCS contract validation via `PF_CORE_REPO_PATH` / `PCS_CORE_REPO_PATH` (`--live` flag)
- Documentation: evidence vocab mapping, key management, updated integration contracts

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
