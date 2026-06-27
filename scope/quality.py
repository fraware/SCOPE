"""Review quality metrics and warnings."""

from __future__ import annotations

from collections import Counter, defaultdict
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
    revoked = [e for e in events if e.get("event_type") == "grant_revoked"]
    quality_warns = [e for e in events if e.get("event_type") == "quality_warning_emitted"]
    grant_used = [e for e in events if e.get("event_type") == "grant_used"]

    decision_types = Counter(
        (e.get("metadata") or {}).get("decision_type", "unknown") for e in decisions
    )
    total_decisions = len(decisions) or 1

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
                    f"under {min_review_seconds} seconds."
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
        action = meta.get("scientific_action_type", "unknown")
        warnings.append(
            {
                "warning_type": "stale_grant_attempt",
                "reason": meta.get("reason", f"Grant expired for action type {action}."),
            }
        )

    for e in violations:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "scope_violation_attempt",
                "reason": meta.get("reason", "Runtime attempted tool outside grant scope."),
            }
        )

    for e in revoked:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "grant_revoked",
                "reason": meta.get("reason", "Grant was revoked."),
            }
        )

    approval_count = (
        decision_types.get("approve", 0) + decision_types.get("approve_narrower_scope", 0)
    )
    approvals_without_comment = sum(
        1
        for e in decisions
        if (e.get("metadata") or {}).get("decision_type")
        in ("approve", "approve_narrower_scope")
        and not (e.get("metadata") or {}).get("has_rationale")
    )
    confidence_values: list[float] = []
    for e in decisions:
        raw = (e.get("metadata") or {}).get("reviewer_confidence")
        if raw is not None:
            confidence_values.append(float(raw))

    metrics = {
        "review_turnaround_time": _median_review_time(decisions),
        "approval_rate": approval_count / total_decisions,
        "rejection_rate": decision_types.get("reject", 0) / total_decisions,
        "request_more_evidence_rate": decision_types.get("request_more_evidence", 0)
        / total_decisions,
        "escalation_rate": decision_types.get("escalate_to_higher_authority", 0) / total_decisions,
        "abstention_rate": decision_types.get("abstain_conflict_or_insufficient_expertise", 0)
        / total_decisions,
        "reviewer_confidence_mean": (
            sum(confidence_values) / len(confidence_values) if confidence_values else None
        ),
        "approval_without_comment_rate": approvals_without_comment / max(approval_count, 1),
        "approval_under_minimum_review_time": len(fast_approvals) / max(approval_count, 1),
        "scope_overbreadth_rate": len(overbroad) / max(len(decisions), 1),
        "stale_grant_rate": len(stale) / max(len(grants), 1),
        "expired_grant_attempt_rate": len(stale) / max(len(grants), 1),
        "scope_violation_attempt_rate": len(violations) / max(len(grants), 1),
        "narrowed_scope_rate": decision_types.get("approve_narrower_scope", 0) / total_decisions,
        "grant_use_count": len(grant_used),
        "grant_revoked_count": len(revoked),
    }

    by_reviewer = _by_reviewer(decisions, fast_approvals)
    by_role = _by_role(decisions)
    by_action_type = _by_action_type(decisions, stale)

    return {
        "report_version": "0.2",
        "policy_version": policy.version,
        "summary": {
            "total_decisions": len(decisions),
            "total_grants": len(grants),
            "total_warnings": len(warnings),
            "grant_use_count": len(grant_used),
        },
        "metrics": metrics,
        "by_reviewer": by_reviewer,
        "by_role": by_role,
        "by_action_type": by_action_type,
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


def _by_reviewer(
    decisions: list[dict[str, Any]], fast_approvals: list[dict[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    fast: dict[str, int] = defaultdict(int)
    for e in decisions:
        actor = e.get("actor_id", "unknown")
        counts[actor] += 1
    for e in fast_approvals:
        actor = e.get("actor_id", "unknown")
        fast[actor] += 1
    return {
        reviewer: {"decisions": counts[reviewer], "fast_approvals": fast.get(reviewer, 0)}
        for reviewer in counts
    }


def _by_role(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    for e in decisions:
        role = e.get("reviewer_role") or (e.get("metadata") or {}).get("reviewer_role", "unknown")
        counts[role] += 1
    return {role: {"decisions": count} for role, count in counts.items()}


def _by_action_type(
    decisions: list[dict[str, Any]], stale: list[dict[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    stale_counts: dict[str, int] = defaultdict(int)
    for e in decisions:
        action = (e.get("metadata") or {}).get("scientific_action_type", "unknown")
        counts[action] += 1
    for e in stale:
        action = (e.get("metadata") or {}).get("scientific_action_type", "unknown")
        stale_counts[action] += 1
    return {
        action: {"decisions": counts[action], "stale_grant_attempts": stale_counts.get(action, 0)}
        for action in counts
    }


def emit_quality_warning(
    warning_type: str,
    reason: str,
) -> dict[str, str]:
    return {"warning_type": warning_type, "reason": reason}
