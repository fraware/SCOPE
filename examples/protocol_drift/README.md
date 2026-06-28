# Protocol Drift Review Example

Demonstrates SCOPE v0.7 handling of protocol modification with explicit `requested_scope`.

AKTA nested record plus trigger with `requested_scope: protocol_draft` produces a packet that restricts approval to draft-level scope. After grant issuance, protocol version drift invalidates the grant at runtime.

## Quick start (AKTA one-shot)

```bash
scope akta review \
  --akta-record examples/protocol_drift/akta_record.json \
  --akta-trigger examples/protocol_drift/review_trigger.json \
  --grant-scope protocol_draft \
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json \
  --decision-rationale "Narrow protocol draft approval only." \
  --out-dir /tmp/akta_review_out
```

For stale-grant behavior after protocol version change, see [stale_grant_attempt/](../stale_grant_attempt/).

Full cross-repo chain: [docs/akta_scope_demo.md](../../docs/akta_scope_demo.md). Output contract: [docs/akta_review_contract.md](../../docs/akta_review_contract.md).
