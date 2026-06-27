# Quality Metrics

SCOPE measures whether review is meaningful.

## Core metrics

- Review turnaround time
- Approval, rejection, escalation, and abstention rates
- Scope overbreadth rate
- Stale grant and scope violation attempt rates
- Narrowed scope rate

## Warnings

| Type | Meaning |
|------|---------|
| `rubber_stamp_risk` | Very fast approvals on high-risk actions |
| `scope_overbreadth` | Approved scope exceeds packet need |
| `stale_grant_attempt` | Grant used after expiration |
| `scope_violation_attempt` | Tool outside grant scope |

## Generate report

```bash
scope quality report --ledger logs/scope_events.jsonl --out report.json
```

Implemented in v0.2: core rates, scope quality rates, reviewer confidence mean,
approval without comment rate, and approval under minimum review time.
Deferred to v0.3: outcome metrics, burden metrics, and confidence variance.
See `policy/quality_metrics.yaml` for `v0_2_status` per metric.

Thresholds are configured in `policy/quality_metrics.yaml`.
