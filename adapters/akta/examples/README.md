# AKTA adapter examples

Sample inputs for `adapters/akta/import_record.py` and `import_trigger.py`.

## Fixtures

| File | Description |
|------|-------------|
| `akta_record.json` | Minimal flat record stub |
| `akta_record_nested.json` | Nested v0.4-style record (golden fixture) |
| `akta_review_trigger_v04.json` | v0.4 trigger with alias fields |
| `review_trigger.json` | Simple flat trigger |

Richer scenario fixtures live under [examples/protocol_change_review/](../../examples/protocol_change_review/).

## Primary integration path (v0.7)

```bash
scope akta review \
  --akta-record adapters/akta/examples/akta_record_nested.json \
  --akta-trigger adapters/akta/examples/akta_review_trigger_v04.json \
  --grant-scope protocol_draft \
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json \
  --decision-rationale "Narrow protocol draft approval only." \
  --out-dir /tmp/akta_review_out
```

Output contract: [docs/akta_review_contract.md](../../docs/akta_review_contract.md).

## Low-level Python import

```python
from adapters.akta.import_record import load_akta_record
from adapters.akta.import_trigger import load_review_trigger

record = load_akta_record("adapters/akta/examples/akta_record_nested.json")
trigger = load_review_trigger("adapters/akta/examples/akta_review_trigger_v04.json")
```

Field mappings: [docs/external_integration_contracts.md](../../docs/external_integration_contracts.md).
