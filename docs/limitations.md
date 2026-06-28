# Limitations

## Implemented in v0.6

- OIDC/JWT identity verification with JWKS or static PEM (`scope identity verify-token`, `SCOPE_OIDC_ENABLED`)
- Signing provider abstraction (local PEM, env key, registry path ref for pilot)
- Institutional RBAC with org units and delegation (`policy/org_rbac.yaml`)
- Review queue auto-assignment, SLA escalation, file locking, static HTML dashboard
- Ledger remote sink (best-effort HTTP append alongside local chain verification)
- Session replication CLI and replicated JSON session store backend
- Runtime violation and expiration ledger recording for PF feedback loop
- VSA live URL fetch adapter with freshness metadata
- PF-Core `pf-core-v0.5` and PCS `pcs-v0.5` export contracts
- Domain overlay validate/list CLI; clinical and genomics mandatory session roles
- REST multi-tenant engine factory via request headers
- Local mock PF/PCS validators in `tests/fixtures/` for CI live-contract tests

## Implemented in v0.5.1

- One-shot `scope akta review` CLI and `POST /v0/akta/review` REST path
- Quality report `--queue-dir` (CLI and REST `GET /v0/quality?queue_dir=...`)
- Public-key-only reviewer registry with `scope key migrate-registry`
- Combined `scope_trust_root_hash` in decision/grant provenance and PCS manifest

## Implemented in v0.5

- Minimal review queue with open/assigned/decided/granted/closed lifecycle (CLI + REST + `.scope/queues/`)
- Reviewer key registry workflow with `scope key list`, signing enforcement, and PCS registry metadata
- AKTA v0.4 trigger field aliases (`admissibility`, `review_route`, constraint fallbacks)
- AKTA evidence alias normalization at packet adapter boundary (`akta_evidence_state` metadata)
- Optional live PF/PCS contract validation when sibling repos are configured

## Implemented in v0.4

- Ed25519 signing on decisions and grants with production-mode grant enforcement
- Public-key-only verification without private key access
- Multi-reviewer sessions with quorum policies and safety veto
- SessionStore persistence (memory, JSON directory, SQLite) with `packet_snapshot`
- Ledger-backed grant use, revocation, and expiration with structured reasons
- First-class `requested_scope` and AKTA `review_route` separation with promotion
- Reviewer packet rendering (markdown/html) with non-certification language
- REST API endpoints for packets, decisions, sessions, grants, signing, and export
- PF-Core and PCS export with manifest hash validation
- All 28 quality metrics computed from ledger events
- Review lifecycle events: `review_assigned`, `review_opened`, `artifact_viewed`
- Optional API key auth on REST endpoints
- Domain overlays modifying role matrices at runtime
- VSA report enrichment in packet `review_artifacts`
- Expanded biosecurity and clinical reviewer scope permissions in policy YAML

## Still limited

- No full enterprise IdP/SAML stack; OIDC/JWT RS256 foundation only
- Registry `signing_key_path` is pilot-only; production HSM/KMS integration is operator-managed
- Remote ledger sink is best-effort; authoritative tamper evidence remains local JSONL chain
- Review queue dashboard is static HTML; no interactive workflow UI
- RBAC is YAML-file based; no live directory sync
- PF/PCS live repo validation still optional; mock validators used when sibling repos absent
- Distributed session store is write-primary with optional read replica; not full CRDT sync
- AKTA live service integration still uses file/HTTP adapters, not in-repo AKTA runtime

## Non-goals

SCOPE does not replace AKTA, PF-Core, VSA, PCS, IRB, biosafety, EHS, or legal compliance. It does not certify scientific safety, reviewer competence, or institutional approval.

## Roadmap

See CHANGELOG for future plans: HSM-backed signing, authoritative remote ledger, interactive review UI, and enterprise directory RBAC sync.
