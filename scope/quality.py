"""Review quality metrics and warnings."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from scope.policy import PolicyStore

WEAK_EVIDENCE_STATES = frozenset(
    {
        "",
        "E0_unknown",
        "E0_no_evidence",
        "E1_hypothesis",
        "E1_weak_signal",
        "E1_anecdotal_or_informal_observation",
        "E2_preliminary",
        "E2_preliminary_signal",
    }
)
HIGH_RISK_ACTION_TYPES = frozenset(
    {
        "A8_tool_or_workflow_mutation",
        "A9_execution_adjacent_or_external_action",
        "A10_publication_or_claim_escalation",
    }
)
APPROVAL_DECISION_TYPES = frozenset({"approve", "approve_narrower_scope"})


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
    packets_created = [e for e in events if e.get("event_type") == "packet_created"]
    review_assigned = [e for e in events if e.get("event_type") == "review_assigned"]
    false_triggers = [e for e in events if e.get("event_type") == "false_review_trigger"]

    decision_types = Counter(
        (e.get("metadata") or {}).get("decision_type", "unknown") for e in decisions
    )
    total_decisions = len(decisions) or 1

    min_review_seconds = thresholds.get("rubber_stamp_min_review_seconds", 20)
    fast_approvals = [
        e
        for e in decisions
        if (e.get("metadata") or {}).get("decision_type") in APPROVAL_DECISION_TYPES
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

    low_evidence_warns = [
        e
        for e in quality_warns
        if (e.get("metadata") or {}).get("warning_type") == "approval_despite_low_evidence"
    ]
    for e in low_evidence_warns:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "approval_despite_low_evidence",
                "reason": meta.get("reason", "Approval despite weak evidence."),
            }
        )

    residual_warns = [
        e
        for e in quality_warns
        if (e.get("metadata") or {}).get("warning_type") == "residual_block_violation"
    ]
    for e in residual_warns:
        meta = e.get("metadata") or {}
        warnings.append(
            {
                "warning_type": "residual_block_violation",
                "reason": meta.get("reason", "AKTA residual blocks not preserved."),
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
        if (e.get("metadata") or {}).get("decision_type") in APPROVAL_DECISION_TYPES
        and not (e.get("metadata") or {}).get("has_rationale")
    )
    confidence_values: list[float] = []
    for e in decisions:
        raw = (e.get("metadata") or {}).get("reviewer_confidence")
        if raw is not None:
            confidence_values.append(float(raw))

    approval_events = [
        e
        for e in decisions
        if (e.get("metadata") or {}).get("decision_type") in APPROVAL_DECISION_TYPES
    ]
    high_risk_approvals = [
        e
        for e in approval_events
        if (e.get("metadata") or {}).get("scientific_action_type") in HIGH_RISK_ACTION_TYPES
    ]
    low_evidence_approvals = [
        e
        for e in approval_events
        if (e.get("metadata") or {}).get("evidence_state") in WEAK_EVIDENCE_STATES
    ]
    akta_block_approvals = [
        e
        for e in approval_events
        if int((e.get("metadata") or {}).get("akta_blocked_tool_count") or 0) > 0
    ]
    residual_preserved = [
        e
        for e in grants
        if (e.get("metadata") or {}).get("residual_blocks_preserved") is True
    ]

    repeat_approvals = _repeat_approval_count(approval_events)
    duplicate_reviews = _duplicate_review_count(decisions)
    unnecessary_reviews = _unnecessary_review_count(decisions)
    packet_decision_times = _packet_decision_durations(events)
    reviewer_load = _reviewer_load(decisions)

    post_protocol_drift = [
        e
        for e in stale
        if "protocol version" in str((e.get("metadata") or {}).get("reason", "")).lower()
    ]
    post_evidence_downgrade = [
        e
        for e in stale
        if "evidence state" in str((e.get("metadata") or {}).get("reason", "")).lower()
    ]
    post_failures = [e for e in stale if (e.get("metadata") or {}).get("post_approval_failure")]

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
        "reviewer_confidence_variance": (
            statistics.pvariance(confidence_values) if len(confidence_values) > 1 else None
        ),
        "approval_without_comment_rate": approvals_without_comment / max(approval_count, 1),
        "approval_under_minimum_review_time": len(fast_approvals) / max(approval_count, 1),
        "repeat_approval_rate": repeat_approvals / max(approval_count, 1),
        "high_risk_approval_rate": len(high_risk_approvals) / max(approval_count, 1),
        "approval_despite_low_evidence_rate": len(low_evidence_approvals) / max(approval_count, 1),
        "approval_despite_akta_block_rate": len(akta_block_approvals) / max(approval_count, 1),
        "scope_overbreadth_rate": len(overbroad) / max(len(decisions), 1),
        "stale_grant_rate": len(stale) / max(len(grants), 1),
        "expired_grant_attempt_rate": len(stale) / max(len(grants), 1),
        "scope_violation_attempt_rate": len(violations) / max(len(grants), 1),
        "narrowed_scope_rate": decision_types.get("approve_narrower_scope", 0) / total_decisions,
        "residual_block_preservation_rate": len(residual_preserved) / max(len(grants), 1),
        "review_queue_length": max(len(packets_created) - len(decisions), 0),
        "open_queue_count": 0,
        "overdue_queue_count": 0,
        "median_time_to_decision": (
            statistics.median(packet_decision_times) if packet_decision_times else None
        ),
        "reviewer_load": reviewer_load,
        "duplicate_review_rate": duplicate_reviews / max(len(decisions), 1),
        "unnecessary_review_rate": unnecessary_reviews / max(len(decisions), 1),
        "false_review_trigger_rate": len(false_triggers) / max(len(packets_created), 1),
        "post_approval_failure_rate": len(post_failures) / max(len(grants), 1),
        "post_approval_protocol_drift_rate": len(post_protocol_drift) / max(len(grants), 1),
        "post_approval_evidence_downgrade_rate": len(post_evidence_downgrade) / max(len(grants), 1),
        "post_approval_runtime_violation_rate": len(violations) / max(len(grants), 1),
        "grant_use_count": len(grant_used),
        "grant_revoked_count": len(revoked),
        "review_assigned_count": len(review_assigned),
    }

    by_reviewer = _by_reviewer(decisions, fast_approvals)
    by_role = _by_role(decisions)
    by_action_type = _by_action_type(decisions, stale)

    return {
        "report_version": "0.5",
        "policy_version": policy.version,
        "summary": {
            "total_decisions": len(decisions),
            "total_grants": len(grants),
            "total_warnings": len(warnings),
            "grant_use_count": len(grant_used),
            "review_queue_length": metrics["review_queue_length"],
        },
        "metrics": metrics,
        "by_reviewer": by_reviewer,
        "by_role": by_role,
        "by_action_type": by_action_type,
        "warnings": warnings,
        "event_counts": dict(Counter(e.get("event_type", "unknown") for e in events)),
    }


def _repeat_approval_count(approval_events: list[dict[str, Any]]) -> int:
    seen: set[tuple[str, str]] = set()
    repeats = 0
    for event in approval_events:
        key = (event.get("packet_id") or "", event.get("actor_id") or "")
        if key in seen:
            repeats += 1
        seen.add(key)
    return repeats


def _duplicate_review_count(decisions: list[dict[str, Any]]) -> int:
    by_packet: dict[str, set[str]] = defaultdict(set)
    duplicates = 0
    for event in decisions:
        packet_id = event.get("packet_id")
        actor = event.get("actor_id")
        if not packet_id or not actor:
            continue
        if actor in by_packet[packet_id]:
            duplicates += 1
        by_packet[packet_id].add(actor)
    return duplicates


def _unnecessary_review_count(decisions: list[dict[str, Any]]) -> int:
    unnecessary = 0
    for event in decisions:
        meta = event.get("metadata") or {}
        if meta.get("decision_type") in APPROVAL_DECISION_TYPES:
            approved = meta.get("approved_scope")
            requested = meta.get("requested_scope")
            if approved == "clarification_only" and requested in (None, "clarification_only"):
                unnecessary += 1
    return unnecessary


def _packet_decision_durations(events: list[dict[str, Any]]) -> list[float]:
    packet_times: dict[str, str] = {}
    durations: list[float] = []
    for event in events:
        if event.get("event_type") == "packet_created" and event.get("packet_id"):
            packet_times[event["packet_id"]] = event.get("timestamp", "")
        if event.get("event_type") == "decision_submitted" and event.get("packet_id"):
            meta = event.get("metadata") or {}
            if meta.get("time_to_decision_seconds") is not None:
                durations.append(float(meta["time_to_decision_seconds"]))
    return durations


def _reviewer_load(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for event in decisions:
        actor = event.get("actor_id") or "unknown"
        counts[actor] += 1
    return dict(counts)


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


def is_weak_evidence(evidence_state: str | None) -> bool:
    return (evidence_state or "") in WEAK_EVIDENCE_STATES
