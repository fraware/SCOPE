# Queue prioritization review (invalid reviewer)

Scenario: queue prioritization (A7) requires `principal_investigator` or `lab_operations_lead`. A `protocol_owner` attempts approval — SCOPE must reject fail-closed.

## Run (expect failure)

```bash
scope packet create \
  --akta-record examples/queue_prioritization_review/akta_record.json \
  --akta-trigger examples/queue_prioritization_review/review_trigger.json \
  --out /tmp/queue_packet.json

scope decision submit \
  --packet /tmp/queue_packet.json \
  --reviewer examples/queue_prioritization_review/reviewer_protocol_owner.json \
  --decision examples/queue_prioritization_review/decision.json \
  --out /tmp/queue_decision.json
```

Expected: decision rejected with role authorization error.

See `evals/scenarios/queue_prioritization_wrong_reviewer.json`.

For v0.7 review queue workflow (10 states), see [docs/quality_metrics.md](../../docs/quality_metrics.md) and root README REST queue endpoints.
