# Multi-role genomics review

Scenario: weak-evidence experimental planning (A6) requires both `domain_scientist` and `protocol_owner`. Use `--session` for session-required summary or `--session-complete` to orchestrate votes and issue a grant in one command.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Aggregated decision (`completed` path) |
| `scope_grant.json` | Issued grant (`completed` path) |
| `summary.json` | Completed AKTA review summary |
| `votes.json` | Reviewer/decision vote manifest for session-complete |
| `reviewer_protocol_owner.json` | Protocol owner reviewer fixture |
| `reviewer_domain_scientist.json` | Domain scientist reviewer fixture |
| `decision_protocol_owner.json` | Vote input for protocol owner |
| `decision_domain_scientist.json` | Vote input for domain scientist |
| `manifest.json` | Artifact inventory and schema versions |
| `expected_verification.json` | Checksums and status expectations |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Quality note after grant issue |

## Regenerate session-required summary

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

## Regenerate completed grant (session-complete)

```bash
scope akta review \
  --akta-trigger examples/weak_evidence_validation_review/review_trigger.json \
  --akta-record examples/weak_evidence_validation_review/akta_record.json \
  --grant-scope single_validation_run_draft \
  --reviewer examples/pilot/multi_role_genomics_review/reviewer_protocol_owner.json \
  --decision-rationale "Multi-role session-complete grant." \
  --out-dir examples/pilot/multi_role_genomics_review \
  --session-complete \
  --votes examples/pilot/multi_role_genomics_review/votes.json \
  --policy policy
```

REST equivalent: pass `session_complete: true` and `votes[]` to `POST /v0/akta/review` or use `scripts/akta_rest_review.py --session-complete --votes ...`.

See `examples/weak_evidence_validation_review/README.md` for the underlying review scenario.
