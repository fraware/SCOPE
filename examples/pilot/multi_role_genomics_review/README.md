# Multi-role genomics review

Scenario: weak-evidence experimental planning (A6) requires both `domain_scientist` and `protocol_owner`. `scope akta review --session` creates a review session instead of issuing a grant immediately.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `summary.json` | Session-required summary (`status: session_required`) |
| `reviewer_protocol_owner.json` | Protocol owner reviewer fixture |
| `reviewer_domain_scientist.json` | Domain scientist reviewer fixture |
| `decision_protocol_owner.json` | Vote input for protocol owner |
| `decision_domain_scientist.json` | Vote input for domain scientist |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Session-pending quality note |

## Regenerate session

```bash
scope akta review \
  --akta-trigger examples/weak_evidence_validation_review/review_trigger.json \
  --akta-record examples/weak_evidence_validation_review/akta_record.json \
  --grant-scope single_validation_run_draft \
  --reviewer examples/weak_evidence_validation_review/reviewer_protocol_owner.json \
  --decision-rationale "Session required for genomics co-review." \
  --out-dir examples/pilot/multi_role_genomics_review \
  --session \
  --policy policy
```

## Complete grant (after regeneration)

```bash
scope review session vote --session <session_id> ...
scope review session issue-grant ...
```

See `examples/weak_evidence_validation_review/README.md` for the full vote workflow.
