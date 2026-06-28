"""Explicit review queue workflow state machine."""

from __future__ import annotations

from scope.errors import ScopeValidationError

QUEUE_STATES = frozenset(
    {
        "open",
        "assigned",
        "in_review",
        "needs_information",
        "escalated",
        "decided",
        "granted",
        "expired",
        "closed",
        "cancelled",
    }
)

TERMINAL_STATUSES: frozenset[str] = frozenset({"granted", "closed", "cancelled"})
OPEN_STATUSES: frozenset[str] = frozenset(
    {"open", "assigned", "in_review", "needs_information", "escalated"}
)
ACTIVE_STATUSES: frozenset[str] = OPEN_STATUSES | frozenset({"decided"})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"assigned", "cancelled", "closed", "expired"}),
    "assigned": frozenset(
        {"in_review", "needs_information", "escalated", "cancelled", "closed", "expired"}
    ),
    "in_review": frozenset(
        {"needs_information", "decided", "escalated", "cancelled", "closed", "expired"}
    ),
    "needs_information": frozenset(
        {"in_review", "escalated", "cancelled", "closed", "expired"}
    ),
    "escalated": frozenset(
        {"in_review", "assigned", "cancelled", "closed", "expired"}
    ),
    "decided": frozenset({"granted", "closed", "cancelled"}),
    "granted": frozenset({"closed"}),
    "expired": frozenset({"open"}),
    "closed": frozenset(),
    "cancelled": frozenset(),
}

FORBIDDEN_GRANT_PATHS: frozenset[tuple[str, str]] = frozenset(
    {
        ("open", "granted"),
        ("assigned", "granted"),
        ("needs_information", "granted"),
        ("expired", "granted"),
        ("in_review", "granted"),
        ("escalated", "granted"),
    }
)


def validate_transition(current: str, new_status: str) -> None:
    """Raise ScopeValidationError when transition is not explicitly allowed."""
    if current not in QUEUE_STATES:
        raise ScopeValidationError(f"Unknown queue status: {current}")
    if new_status not in QUEUE_STATES:
        raise ScopeValidationError(f"Unknown queue status: {new_status}")
    if (current, new_status) in FORBIDDEN_GRANT_PATHS:
        raise ScopeValidationError(
            f"Invalid transition {current} -> {new_status}: "
            "grants require decided status (decided -> granted only)"
        )
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if new_status not in allowed:
        raise ScopeValidationError(
            f"Invalid queue transition {current} -> {new_status}; "
            f"allowed: {sorted(allowed)}"
        )


def can_transition(current: str, new_status: str) -> bool:
    try:
        validate_transition(current, new_status)
        return True
    except ScopeValidationError:
        return False


def requires_reopen_for_grant(status: str) -> bool:
    return status == "expired"
