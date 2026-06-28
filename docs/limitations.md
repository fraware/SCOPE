# Limitations

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

- No real identity provider (IdP) binding; reviewer identity is caller-supplied
- Local Ed25519 key signing only; no HSM or institutional key management
- No external tamper-evident ledger; JSONL ledger is local and append-only
- No persistent review queue database or workflow engine
- No institutional RBAC beyond policy YAML role matrices
- PF-Core and PCS validation is local schema/hash checking only
- Session store SQLite backend is single-node; not distributed
- AKTA, PF-Core, PCS, and VSA live service integration requires external repos

## Non-goals

SCOPE does not replace AKTA, PF-Core, VSA, PCS, IRB, biosafety, EHS, or legal compliance. It does not certify scientific safety, reviewer competence, or institutional approval.

## Roadmap

See CHANGELOG for future plans: IdP integration, distributed ledger hooks, review queue UI, and institutional RBAC.
