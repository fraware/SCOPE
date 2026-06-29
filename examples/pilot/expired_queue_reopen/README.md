# Expired queue reopen

Scenario: a review queue entry expires while in review; operators must reopen before grant issuance.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `review_queue_expired.json` | Queue entry in `expired` status |
| `review_queue_reopened.json` | Same entry after `reopen` (`open` status) |
| `scope_events.jsonl` | Ledger trail |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Quality metrics snippet |

## Workflow

1. Assign reviewer and mark `in_review`
2. `expire` when SLA elapses
3. `reopen` before resuming review
4. Grant issuance is blocked until reopen

`mark_granted` from `expired` raises a validation error directing operators to reopen first.
