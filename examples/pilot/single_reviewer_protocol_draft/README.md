# Single reviewer protocol draft

Scenario: protocol owner approves a narrowed `protocol_draft` scope for an A5 protocol modification (protocol drift demo inputs).

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Reviewer decision |
| `scope_grant.json` | Issued grant |
| `summary.json` | Completed AKTA review summary |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Policy version from quality report |

## Regenerate

```bash
scope akta review \
  --akta-trigger examples/protocol_drift/review_trigger.json \
  --akta-record examples/protocol_drift/akta_record.json \
  --grant-scope protocol_draft \
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json \
  --decision-rationale "Pilot single-reviewer protocol draft approval." \
  --out-dir examples/pilot/single_reviewer_protocol_draft \
  --policy policy
```

Expected: `summary.json` status `completed`, approved scope `protocol_draft`.
