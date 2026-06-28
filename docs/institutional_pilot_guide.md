# Institutional Pilot Guide

This guide supports workshop, funder, and lab pilots of SCOPE v0.4 alongside AKTA.

## Pilot posture

- Use SCOPE for structured review coordination and bounded grants
- Treat rendered packets and PCS exports as audit artifacts, not certifications
- Keep reviewer keys local; distribute public keys to auditors only
- Enable production mode (`SCOPE_PRODUCTION_MODE=true`) for grant enforcement

## Workshop flow (90 minutes)

1. **AKTA evaluation** — Present a scientific action; AKTA emits record + review trigger
2. **SCOPE packet** — `scope packet create` and `scope packet render` for reviewers
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
