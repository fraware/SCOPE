# Institutional Pilot Guide

This guide supports workshop, funder, and lab pilots of SCOPE v0.7 alongside AKTA.

## v0.7 institutional additions

- **Identity assurance (IAL0–IAL4)** on every decision and grant provenance
- **Authority checks** with two-stage org RBAC then SCOPE scope policy separation
- **Signing assurance (SAL0–SAL4)** with production minimums in `policy/minimum_signing_assurance.yaml`
- **Ledger delivery modes**: `best_effort`, `at_least_once` (spool), `fail_closed` for high-risk events
- **Review queue workflow** (10 states) with REST, CLI, and static HTML dashboard
- **Frozen AKTA review contract** (`summary.json` schema, `scope akta review` primary path)

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

Sample artifacts: `examples/institutional_pilot/`

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
scope quality report --ledger pilot_events.jsonl --out quality_report.json
```

Report includes reviewer metrics, warnings, and event counts. Non-certification: metrics describe process quality, not scientific validity.

## Lab integration checklist

- [ ] Policy YAML reviewed and version-pinned
- [ ] Reviewer roles mapped to lab personnel
- [ ] Ed25519 keypairs generated per reviewer role
- [ ] PF-Core runtime configured to enforce grant obligations
- [ ] Ledger path configured (`SCOPE_LEDGER_PATH`)
- [ ] Session store directory secured (if using json/sqlite)
- [ ] Pilot limitations documented to participants

## Limitations

See [limitations.md](limitations.md). Pilots should not rely on SCOPE for IdP, RBAC, biosecurity clearance, or clinical oversight.

## Related docs

- [reviewer_guide.md](reviewer_guide.md) — role-specific guidance
- [trusted_boundary.md](trusted_boundary.md) — trust assumptions
- [akta_scope_demo.md](akta_scope_demo.md) — full cross-repo demo
