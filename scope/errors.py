"""SCOPE error types."""

from __future__ import annotations


class ScopeError(Exception):
    """Base error for SCOPE operations."""


class SchemaValidationError(ScopeError):
    """Artifact failed JSON schema validation."""


class PolicyError(ScopeError):
    """Policy configuration or lookup error."""


class RoleValidationError(ScopeError):
    """Reviewer role is invalid or not authorized for action."""


class ScopeValidationError(ScopeError):
    """Approval scope is unknown or violates hierarchy rules."""


class DecisionValidationError(ScopeError):
    """Decision failed semantic validation."""


class GrantValidationError(ScopeError):
    """Grant issuance or check failed."""


class ExpirationError(ScopeError):
    """Grant has expired or context invalidated it."""


class LedgerError(ScopeError):
    """Ledger operation failed."""
