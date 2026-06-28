"""Tests for signing provider abstraction."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scope.errors import ScopeValidationError
from scope.signing import Ed25519Signer
from scope.signing_providers import LocalPemProvider, resolve_signing_provider


def test_local_pem_provider_signs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        key = Path(tmp) / "key.pem"
        pub = Path(tmp) / "key.pub"
        Ed25519Signer.generate_keypair(key, pub)
        provider = LocalPemProvider(key)
        signer = provider.get_signer()
        assert signer.public_key_ref()


def test_registry_provider_requires_signing_key_path() -> None:
    with pytest.raises(ScopeValidationError, match="No registry entry|signing_key_path"):
        resolve_signing_provider(
            "registry",
            policy_dir="policy/",
            reviewer_id="nonexistent_reviewer_xyz",
        ).get_signer()
