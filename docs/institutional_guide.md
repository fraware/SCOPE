# Institutional Guide

Institutions adopting SCOPE v0.7 should start with the [institutional pilot guide](institutional_pilot_guide.md), which covers workshop flow, checklist, and v0.7 features (identity assurance, signing assurance, review queue, ledger delivery).

## Adoption checklist

1. Configure and version-pin `policy/` files (`scope-core-v0.7`) for local role assignments and scope boundaries
2. Map lab personnel to reviewer roles; generate Ed25519 keypairs and register public keys
3. Integrate AKTA review triggers via `scope akta review` or `scope packet create`
4. Enable production mode (`SCOPE_PRODUCTION_MODE=true`) and minimum signing assurance for grant enforcement
5. Optional: OIDC identity (`SCOPE_OIDC_*`) and org RBAC (`SCOPE_ENFORCE_RBAC=true`)
6. Enforce grants at runtime via PF-Core or equivalent
7. Archive SCOPE ledger events with PCS release packages
8. Monitor quality reports for rubber-stamping and scope violations

## Evidence for auditors

- Who reviewed (role, ID, identity assurance level, authority checks)
- What scope was approved and what remained blocked
- Signing assurance level on decisions and grants
- When grants expired and whether runtime respected grants
- Trust root hashes binding policy and key registry

SCOPE provides the authorization trail; it does not certify scientific correctness or regulatory compliance.

## Related documentation

- [institutional_pilot_guide.md](institutional_pilot_guide.md) — workshop and lab integration
- [trusted_boundary.md](trusted_boundary.md) — trust assumptions
- [limitations.md](limitations.md) — in-repo vs external boundaries
- [reviewer_guide.md](reviewer_guide.md) — role-specific guidance
