# Institutional Pilot Examples

Sample artifacts for SCOPE v0.7 institutional pilot workshops. See [docs/institutional_pilot_guide.md](../../docs/institutional_pilot_guide.md).

| File | Description |
|------|-------------|
| akta_record.json | AKTA scientific action record |
| review_trigger.json | AKTA review trigger with explicit requested_scope |
| scope_packet.json | SCOPE review packet |
| scope_decision.json | Reviewer decision (unsigned) |
| scope_grant.json | Bounded authorization grant |
| quality_report.json | Ledger quality analytics |
| scope_events.jsonl | Ledger event trail |
| reviewer_protocol_owner.json | Reviewer identity fixture |
| decision.json | Decision input fixture |
| current_context.json | Runtime context for grant check |

Artifacts use policy bundle `scope-core-v0.7`. In production mode, sign decisions before grant issue; see [docs/trusted_boundary.md](../../docs/trusted_boundary.md).

To regenerate PCS export from these artifacts:

```bash
scope export pcs \
  --packet examples/institutional_pilot/scope_packet.json \
  --decision examples/institutional_pilot/scope_decision.json \
  --grant examples/institutional_pilot/scope_grant.json \
  --out dist/pcs_scope_artifact/ \
  --validate
```
