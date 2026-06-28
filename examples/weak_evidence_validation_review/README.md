# Weak evidence validation review

Scenario: AKTA flags experimental planning (A6) with weak evidence (`E1_weak_signal`). Protocol owner and domain scientist co-review and narrow approval to `single_validation_run_draft`.

A6 requires a multi-reviewer session (`require_all` for `protocol_owner` and `domain_scientist`).

## Run

```bash
scope packet create \
  --akta-record examples/weak_evidence_validation_review/akta_record.json \
  --akta-trigger examples/weak_evidence_validation_review/review_trigger.json \
  --out /tmp/weak_evidence_packet.json

scope review session create \
  --packet /tmp/weak_evidence_packet.json \
  --out /tmp/weak_evidence_session.json \
  --session-store json --session-dir /tmp/sessions

scope review session vote \
  --session /tmp/weak_evidence_session.json \
  --packet /tmp/weak_evidence_packet.json \
  --reviewer examples/weak_evidence_validation_review/reviewer_protocol_owner.json \
  --decision examples/weak_evidence_validation_review/decision.json \
  --out /tmp/weak_evidence_decision_po.json \
  --session-store json --session-dir /tmp/sessions

scope review session vote \
  --session /tmp/weak_evidence_session.json \
  --packet /tmp/weak_evidence_packet.json \
  --reviewer examples/reviewer_domain_scientist.json \
  --decision examples/weak_evidence_validation_review/decision_ds.json \
  --out /tmp/weak_evidence_decision_ds.json \
  --session-store json --session-dir /tmp/sessions

scope review session issue-grant \
  --session /tmp/weak_evidence_session.json \
  --packet /tmp/weak_evidence_packet.json \
  --decision /tmp/weak_evidence_decision_po.json \
  --decision /tmp/weak_evidence_decision_ds.json \
  --out /tmp/weak_evidence_grant.json \
  --session-store json --session-dir /tmp/sessions

scope grant check \
  --grant /tmp/weak_evidence_grant.json \
  --requested-tool experiment_planner.create_validation_plan \
  --context examples/weak_evidence_validation_review/current_context.json

scope grant check \
  --grant /tmp/weak_evidence_grant.json \
  --requested-tool robot_queue.submit \
  --context examples/weak_evidence_validation_review/current_context.json
```

Expected: validation planning allowed; `robot_queue.submit` blocked.

See `evals/scenarios/weak_evidence_validation_review.json`.
