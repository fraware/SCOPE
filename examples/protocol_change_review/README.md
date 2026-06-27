# Protocol change review (Milestone 7 demo)

Primary proof-of-life scenario from design spec section 26/32: AKTA `review_required` for active protocol update becomes a narrower `protocol_draft` grant.

## Run

```bash
scope packet create \
  --akta-record examples/protocol_change_review/akta_record.json \
  --akta-trigger examples/protocol_change_review/review_trigger.json \
  --out /tmp/packet.json

scope decision submit \
  --packet /tmp/packet.json \
  --reviewer examples/protocol_change_review/reviewer_protocol_owner.json \
  --decision examples/protocol_change_review/decision.json \
  --out /tmp/decision.json

scope grant issue \
  --packet /tmp/packet.json \
  --decision /tmp/decision.json \
  --out /tmp/grant.json

scope grant check \
  --grant /tmp/grant.json \
  --requested-tool protocol_editor.draft_change \
  --context examples/protocol_change_review/current_context.json

scope export pf --grant /tmp/grant.json --out dist/pf_obligation.json

scope export pcs \
  --packet /tmp/packet.json \
  --decision /tmp/decision.json \
  --grant /tmp/grant.json \
  --out dist/pcs_scope_artifact/
```

Expected: `protocol_editor.draft_change` allowed; `robot_queue.submit` blocked; grant invalid after protocol version change.
