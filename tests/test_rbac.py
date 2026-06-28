"""Tests for institutional RBAC."""

from __future__ import annotations

import pytest

from scope.errors import ScopeValidationError
from scope.rbac import check_rbac_permission, resolve_effective_roles


def test_resolve_effective_roles_includes_delegation() -> None:
    roles = resolve_effective_roles("ds2", "policy/")
    assert "domain_scientist" in roles


def test_rbac_denies_unknown_reviewer() -> None:
    with pytest.raises(ScopeValidationError, match="RBAC"):
        check_rbac_permission("unknown_xyz", "domain_scientist", "submit_decisions", "policy/")
