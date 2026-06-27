# Changelog

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
