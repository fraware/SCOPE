# Needs information flow

Scenario: reviewer requests additional information; queue transitions `in_review` -> `needs_information` -> `in_review` before a decision.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `review_queue_needs_information.json` | Queue in `needs_information` with reason |
| `review_queue_in_review.json` | Queue after `mark_information_received` |
| `reviewer_protocol_owner.json` | Assigned reviewer |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Quality metrics snippet |

## Workflow

1. Assign reviewer, mark `in_review`
2. `mark_needs_information(reason=...)` when data is missing
3. `mark_information_received()` when submitter provides data
4. Proceed to `mark_decided` / `mark_granted`

Direct transitions from `needs_information` to `decided` or `granted` are forbidden.
