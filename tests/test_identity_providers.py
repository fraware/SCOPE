"""Tests for identity providers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scope.errors import ScopeValidationError
from scope.identity_providers import OidcProvider, SamlProvider, resolve_identity_provider

ROOT = Path(__file__).resolve().parent.parent


def test_resolve_oidc_provider() -> None:
    provider = resolve_identity_provider("oidc", policy_dir=ROOT / "policy")
    assert isinstance(provider, OidcProvider)


def test_saml_provider_from_json(tmp_path: Path) -> None:
    assertion = {
        "attributes": {
            "name_id": "ds1",
            "role": "domain_scientist",
            "groups": ["scope-domain-scientist"],
        }
    }
    path = tmp_path / "assertion.json"
    path.write_text(json.dumps(assertion), encoding="utf-8")
    provider = SamlProvider(policy_dir=ROOT / "policy", assertion_path=path)
    identity = provider.verify(json.dumps(assertion))
    assert identity.reviewer_id == "ds1"
    assert identity.role == "domain_scientist"


def test_saml_provider_missing_assertion() -> None:
    provider = SamlProvider(policy_dir=ROOT / "policy")
    with pytest.raises(ScopeValidationError, match="SAML"):
        provider.verify("not-json")
