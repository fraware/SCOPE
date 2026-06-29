# Institutional Pilot Guide

This guide supports workshop, funder, and lab pilots of SCOPE v0.8 alongside AKTA.

## v0.8 institutional additions

- **`scope akta review --session`** for multi-role packets — session summary schema and vote workflow before grant issue — [akta_review_contract.md](akta_review_contract.md)
- **`--reviewer-id` binding** when using `--signing-provider registry` — [key_management.md](key_management.md)
- **Session grant provenance** on multi-reviewer grants (contributing IAL/SAL, authority checks, veto roles, quorum hash)
- **Pilot fixture pack** — [examples/pilot/](../examples/pilot/) with five regenerated scenarios

## v0.7 institutional additions

- **Identity assurance (IAL0–IAL4)** on every decision and grant provenance — [identity_assurance.md](identity_assurance.md)
- **Authority checks** with two-stage org RBAC then SCOPE scope policy separation — [rbac_scope_authority.md](rbac_scope_authority.md)
- **Signing assurance (SAL0–SAL4)** with production minimums in `policy/minimum_signing_assurance.yaml` — [signing_assurance.md](signing_assurance.md)
- **Ledger delivery modes**: `best_effort`, `at_least_once` (spool), `fail_closed` for high-risk events (`SCOPE_LEDGER_DELIVERY_MODE`)
- **Review queue workflow** (10 states) with REST, CLI, and static HTML dashboard
- **Frozen AKTA review contract** (`summary.json` schema, `scope akta review` primary path) — [akta_review_contract.md](akta_review_contract.md)

## v0.6 institutional additions

- OIDC/JWT reviewer identity: `scope identity verify-token`, `--identity-token` on decisions
- Signing providers: `--signing-provider env|registry|local`
- Org RBAC: `policy/org_rbac.yaml`, `--enforce-rbac` / `SCOPE_ENFORCE_RBAC=true`
- Review queue auto-assign, SLA escalation, static dashboard
- Runtime violation ledger loop: `scope ledger record-violation`
- Session replication: `scope review session replicate --source --dest`

## Pilot posture

- Use SCOPE for structured review coordination and bounded grants
- Treat rendered packets and PCS exports as audit artifacts, not certifications
- Keep reviewer keys local; distribute public keys to auditors only
- Enable production mode (`SCOPE_PRODUCTION_MODE=true`) for grant enforcement

## Workshop flow (90 minutes)

1. **AKTA evaluation** — Present a scientific action; AKTA emits record + review trigger
2. **SCOPE packet** — `scope packet create` or `scope akta review` for one-shot packet/decision/grant
3. **Review** — Reviewers read rendered packet (permits/denies, checklist, warnings)
4. **Decision** — `scope decision submit` (unsigned OK in production mode)
5. **Sign** — `scope decision sign` with pilot reviewer key
6. **Grant** — `scope grant issue` with signed decision
7. **Verify** — `scope verify --public-key` for auditor demonstration
8. **Export** — PCS bundle for institutional record-keeping

Sample artifacts: [examples/institutional_pilot/](../examples/institutional_pilot/). v0.8 pilot pack: [examples/pilot/](../examples/pilot/).

## Multi-reviewer pilot (A6)

Use persistent session storage so votes survive process restarts:

```bash
scope review session create --packet packet.json --out session.json \
  --session-store json --session-dir ./pilot_sessions
```

Collect votes from `domain_scientist` and `protocol_owner`, then issue grant from session.

## Funder reporting

Export quality report from ledger:

```bash
scope quality report --ledger pilot_events.jsonl --out quality_report.json \
  --queue-dir .scope/queues
```

Report includes reviewer metrics, warnings, queue counts, and event counts. Non-certification: metrics describe process quality, not scientific validity. See [quality_metrics.md](quality_metrics.md).

## Lab integration checklist

- [ ] Policy YAML reviewed and version-pinned (`scope-core-v0.8`)
- [ ] Reviewer roles mapped to lab personnel
- [ ] Ed25519 keypairs generated per reviewer role; public keys registered
- [ ] PF-Core runtime configured to enforce grant obligations
- [ ] Ledger path configured (`SCOPE_LEDGER_PATH`)
- [ ] Ledger delivery mode set for institutional risk tolerance
- [ ] Session store directory secured (if using json/sqlite)
- [ ] Pilot limitations documented to participants

## Limitations

See [limitations.md](limitations.md). Pilots should not rely on SCOPE for full enterprise IdP, live directory sync, biosecurity clearance, or clinical oversight.

## Related docs

- [reviewer_guide.md](reviewer_guide.md) — role-specific guidance
- [trusted_boundary.md](trusted_boundary.md) — trust assumptions
- [akta_scope_demo.md](akta_scope_demo.md) — full cross-repo demo
- [key_management.md](key_management.md) — key registry workflow
