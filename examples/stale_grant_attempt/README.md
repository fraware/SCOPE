# Stale grant attempt

Scenario: a grant issued at `protocol_v3` must fail when the runtime context advances to `protocol_v4`.

## Run

```bash
scope packet create \
  --akta-record examples/stale_grant_attempt/akta_record.json \
  --akta-trigger examples/stale_grant_attempt/review_trigger.json \
  --out /tmp/stale_packet.json

scope decision submit \
  --packet /tmp/stale_packet.json \
  --reviewer examples/stale_grant_attempt/reviewer_protocol_owner.json \
  --decision examples/stale_grant_attempt/decision.json \
  --out /tmp/stale_decision.json

scope grant issue \
  --packet /tmp/stale_packet.json \
  --decision /tmp/stale_decision.json \
  --out /tmp/stale_grant.json

scope grant check \
  --grant /tmp/stale_grant.json \
  --requested-tool protocol_editor.draft_change \
  --context examples/stale_grant_attempt/current_context.json

scope grant check \
  --grant /tmp/stale_grant.json \
  --requested-tool protocol_editor.draft_change \
  --context examples/stale_grant_attempt/stale_context.json
```

Expected: first check ALLOWED; second check BLOCKED (stale after protocol version change).

See `evals/scenarios/stale_grant_after_protocol_change.json`.
