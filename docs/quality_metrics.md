# Quality Metrics

SCOPE measures whether review is meaningful through ledger-backed analytics.

## Core metrics

| Metric | Description |
|--------|-------------|
| `review_turnaround_time` | Median reviewer duration (seconds) per decision |
| `approval_rate` / `rejection_rate` | Decision type distribution |
| `request_more_evidence_rate` | Rate of evidence requests |
| `escalation_rate` / `abstention_rate` | Escalation and abstention rates |
| `reviewer_confidence_mean` | Mean reviewer confidence score |
| `reviewer_confidence_variance` | Variance of reviewer confidence scores |

## Rubber-stamp detection

| Metric | Description |
|--------|-------------|
| `approval_without_comment_rate` | Approvals lacking rationale |
| `approval_under_minimum_review_time` | Fast approvals below threshold |
| `repeat_approval_rate` | Same reviewer approving same packet twice |
| `high_risk_approval_rate` | Approvals on A8/A9/A10 action types |
| `approval_despite_low_evidence_rate` | Approvals when evidence is E0/E1/E2 |
| `approval_despite_akta_block_rate` | Approvals when AKTA blocked tools present |

## Scope quality

| Metric | Description |
|--------|-------------|
| `scope_overbreadth_rate` | Approvals exceeding requested scope |
| `stale_grant_rate` / `expired_grant_attempt_rate` | Post-expiration grant use |
| `scope_violation_attempt_rate` | Runtime tool violations |
| `narrowed_scope_rate` | `approve_narrower_scope` decisions |
| `residual_block_preservation_rate` | Grants preserving AKTA blocked tools |

## Review burden

| Metric | Description |
|--------|-------------|
| `review_queue_length` | Packets created minus decisions submitted |
| `median_time_to_decision` | Packet creation to decision latency |
| `reviewer_load` | Decisions per reviewer (map) |
| `duplicate_review_rate` | Duplicate reviewer participation per packet |
| `unnecessary_review_rate` | Clarification-only approvals on low-scope packets |
| `false_review_trigger_rate` | Packets created despite `no_review_needed` |

## Post-approval outcomes

| Metric | Description |
|--------|-------------|
| `post_approval_failure_rate` | Expired grant attempts after approval |
| `post_approval_protocol_drift_rate` | Expiration due to protocol version change |
| `post_approval_evidence_downgrade_rate` | Expiration due to evidence state change |
| `post_approval_runtime_violation_rate` | Runtime scope violations per grant |

## Warnings

| Type | Meaning |
|------|---------|
| `rubber_stamp_risk` | Very fast approvals on high-risk actions |
| `scope_overbreadth` | Approved scope exceeds packet need |
| `approval_despite_low_evidence` | Approval with weak evidence state |
| `residual_block_violation` | Approval may not preserve AKTA blocks |
| `stale_grant_attempt` | Grant used after expiration |
| `scope_violation_attempt` | Tool outside grant scope |

## Review queue (v0.5)

| Metric | Description |
|--------|-------------|
| `open_queue_count` | Queue entries in `open` or `assigned` status (file-backed `.scope/queues/`) |
| `overdue_queue_count` | Open/assigned entries past `due_at` SLA timestamp |

Queue status lifecycle: `open` → `assigned` → `decided` → `granted` (or `closed`).

## Generate report

```bash
scope quality report --ledger logs/scope_events.jsonl --out report.json
```

All metrics in `policy/quality_metrics.yaml` are implemented in v0.5 (`v0_4_status: implemented` for core metrics; `v0_5_status: implemented` for queue metrics).
Thresholds are configured in the same file.

## Ledger events

Quality analytics derive from:

- `packet_created`, `review_assigned`, `review_opened`, `artifact_viewed`
- `decision_submitted` (with evidence state, AKTA block count, timing metadata)
- `grant_issued` (with `residual_blocks_preserved`)
- `grant_used`, `grant_expired`, `grant_revoked`, `runtime_scope_violation_attempted`
- `quality_warning_emitted`, `false_review_trigger`
