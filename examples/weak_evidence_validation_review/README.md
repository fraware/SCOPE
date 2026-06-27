# Weak evidence validation review

Scenario: AKTA flags experimental planning with weak evidence (`E1_weak_signal`). The protocol owner narrows approval to `single_validation_run_draft` instead of broader execution scope.

## Run

```bash
scope packet create \
  --akta-record examples/weak_evidence_validation_review/akta_record.json \
  --akta-trigger examples/weak_evidence_validation_review/review_trigger.json \
  --out /tmp/weak_evidence_packet.json

scope decision submit \
  --packet /tmp/weak_evidence_packet.json \
  --reviewer examples/weak_evidence_validation_review/reviewer_protocol_owner.json \
  --decision examples/weak_evidence_validation_review/decision.json \
  --out /tmp/weak_evidence_decision.json

scope grant issue \
  --packet /tmp/weak_evidence_packet.json \
  --decision /tmp/weak_evidence_decision.json \
  --out /tmp/weak_evidence_grant.json

scope grant check \
  --grant /tmp/weak_evidence_grant.json \
  --requested-tool experiment_planner.create_validation_plan \
  --context examples/weak_evidence_validation_review/current_context.json
```

Expected: validation planning allowed; `robot_queue.submit` blocked.

See also `evals/scenarios/weak_evidence_validation_review.json`.
