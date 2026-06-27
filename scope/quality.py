"""Review quality metrics and warnings."""

from __future__ import annotations

from collections import Counter
from typing import Any

from scope.policy import PolicyStore


def analyze_ledger(events: list[dict[str, Any]], policy: PolicyStore) -> dict[str, Any]:
    """Generate quality report from ledger events."""
    thresholds = policy.quality_metrics.get("thresholds", {})
    warnings: list[dict[str, str]] = []

    decisions = [e for e in events if e.get("event_type") == "decision_submitted"]
    grants = [e for e in events if e.get("event_type") == "grant_issued"]
    violations = [e for e in events if e.get("event_type") == "runtime_scope_violation_attempted"]
    stale = [e for e in events if e.get("event_type") == "grant_expired"]
    quality_warns = [e for e in events if e.get("event_type") == "quality_warning_emitted"]

    decision_types = Counter(
        (e.get("metadata") or {}).get("decision_type", "unknown") for e in decisions
    )
    total_decisions = len(decisions) or 1

    # Rubber-stamp detection from metadata
    min_review_seconds = thresholds.get("rubber_stamp_min_review_seconds", 20)
    fast_approvals = [
        e
        for e in decisions
        if (e.get("metadata") or {}).get("decision_type") in ("approve", "approve_narrower_scope")
        and ((e.get("metadata") or {}).get("review_duration_seconds") or 999) < min_review_seconds
    ]
    if len(fast_approvals) >= thresholds.get("rubber_stamp_high_risk_count", 10):
        warnings.append(
            {
                "warning_type": "rubber_stamp_risk",
                "reason": (
                    f"Reviewer approved {len(fast_approvals)} actions with median review time "
                    f"under {thresholds.get('rubber_stamp_min_review_seconds', 20)} seconds."
                ),
            }
        )

    overbroad = [
        e
        for e in quality_warns
        if (e.get("metadata") or {}).get("warning_type") == "scope_overbreadth"
    ]
    for e in overbroad:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "scope_overbreadth",
                "reason": meta.get("reason", "Scope overbreadth detected."),
            }
        )

    for e in stale:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "stale_grant_attempt",
                "reason": meta.get("reason", "Grant expired after context change."),
            }
        )

    for e in violations:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "scope_violation_attempt",
                "reason": meta.get(
                    "reason", "Runtime attempted tool outside grant scope."
                ),
            }
        )

    metrics = {
        "review_turnaround_time": _median_review_time(decisions),
        "approval_rate": decision_types.get("approve", 0) / total_decisions
        + decision_types.get("approve_narrower_scope", 0) / total_decisions,
        "rejection_rate": decision_types.get("reject", 0) / total_decisions,
        "request_more_evidence_rate": decision_types.get("request_more_evidence", 0)
        / total_decisions,
        "escalation_rate": decision_types.get("escalate_to_higher_authority", 0) / total_decisions,
        "abstention_rate": decision_types.get("abstain_conflict_or_insufficient_expertise", 0)
        / total_decisions,
        "scope_overbreadth_rate": len(overbroad) / max(len(decisions), 1),
        "stale_grant_rate": len(stale) / max(len(grants), 1),
        "expired_grant_attempt_rate": len(stale) / max(len(grants), 1),
        "scope_violation_attempt_rate": len(violations) / max(len(grants), 1),
        "narrowed_scope_rate": decision_types.get("approve_narrower_scope", 0) / total_decisions,
    }

    return {
        "report_version": "0.1",
        "policy_version": policy.version,
        "metrics": metrics,
        "warnings": warnings,
        "event_counts": dict(Counter(e.get("event_type", "unknown") for e in events)),
    }


def _median_review_time(decisions: list[dict[str, Any]]) -> float | None:
    durations: list[float] = []
    for event in decisions:
        raw = (event.get("metadata") or {}).get("review_duration_seconds")
        if raw is not None:
            durations.append(float(raw))
    if not durations:
        return None
    durations.sort()
    mid = len(durations) // 2
    if len(durations) % 2:
        return durations[mid]
    return (durations[mid - 1] + durations[mid]) / 2.0


def emit_quality_warning(
    warning_type: str,
    reason: str,
) -> dict[str, str]:
    return {"warning_type": warning_type, "reason": reason}
