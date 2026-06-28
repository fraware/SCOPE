"""Digital signatures for SCOPE decisions and grants."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from scope.errors import ScopeValidationError
from scope.hash import compute_hash


class Signer(ABC):
    """Pluggable signer interface."""

    @abstractmethod
    def public_key_ref(self) -> str:
        """Return reference identifier for the reviewer's public key."""

    @abstractmethod
    def sign(self, payload: dict[str, Any], hash_field: str) -> str:
        """Return base64-encoded signature over canonical payload hash."""

    @abstractmethod
    def verify(
        self,
        payload: dict[str, Any],
        hash_field: str,
        signature: str,
        public_key_ref: str,
    ) -> bool:
        """Verify signature against payload."""


class Verifier(ABC):
    """Pluggable verifier interface (public key only)."""

    @abstractmethod
    def public_key_ref(self) -> str:
        """Return reference identifier for the reviewer's public key."""

    @abstractmethod
    def verify(
        self,
        payload: dict[str, Any],
        hash_field: str,
        signature: str,
        public_key_ref: str,
    ) -> bool:
        """Verify signature against payload."""


class Ed25519Signer(Signer):
    """Local Ed25519 signer using cryptography library."""

    ALGORITHM = "ed25519"

    def __init__(self, private_key_path: str | Path, public_key_ref: str | None = None) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        path = Path(private_key_path)
        pem = path.read_bytes()
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ScopeValidationError("Private key must be Ed25519")
        self._private_key = key
        self._public_key = key.public_key()
        self._public_key_ref = public_key_ref or compute_hash(
            {
                "public_key_pem": self._public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("ascii")
            }
        )

    @classmethod
    def generate_keypair(cls, private_path: str | Path, public_path: str | Path) -> str:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        Path(private_path).write_bytes(private_pem)
        Path(public_path).write_bytes(public_pem)
        return compute_hash({"public_key_pem": public_pem.decode("ascii")})

    def public_key_ref(self) -> str:
        return self._public_key_ref

    def sign(self, payload: dict[str, Any], hash_field: str) -> str:
        if hash_field not in payload:
            raise ScopeValidationError(f"Missing {hash_field} for signing")
        digest = payload[hash_field].removeprefix("sha256:")
        sig = self._private_key.sign(bytes.fromhex(digest))
        return base64.b64encode(sig).decode("ascii")

    def verify(
        self,
        payload: dict[str, Any],
        hash_field: str,
        signature: str,
        public_key_ref: str,
    ) -> bool:
        from cryptography.exceptions import InvalidSignature

        if public_key_ref != self._public_key_ref:
            return False
        if hash_field not in payload:
            return False
        digest = payload[hash_field].removeprefix("sha256:")
        try:
            self._public_key.verify(base64.b64decode(signature), bytes.fromhex(digest))
            return True
        except InvalidSignature:
            return False


class Ed25519PublicVerifier(Verifier):
    """Ed25519 verifier using public PEM only (no private key required)."""

    ALGORITHM = "ed25519"

    def __init__(self, public_key_path: str | Path, public_key_ref: str | None = None) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        path = Path(public_key_path)
        pem = path.read_bytes()
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, Ed25519PublicKey):
            raise ScopeValidationError("Public key must be Ed25519")
        self._public_key = key
        self._public_key_ref = public_key_ref or compute_hash(
            {"public_key_pem": pem.decode("ascii")}
        )

    def public_key_ref(self) -> str:
        return self._public_key_ref

    def verify(
        self,
        payload: dict[str, Any],
        hash_field: str,
        signature: str,
        public_key_ref: str,
    ) -> bool:
        from cryptography.exceptions import InvalidSignature

        if public_key_ref != self._public_key_ref:
            return False
        if hash_field not in payload:
            return False
        digest = payload[hash_field].removeprefix("sha256:")
        try:
            self._public_key.verify(base64.b64decode(signature), bytes.fromhex(digest))
            return True
        except InvalidSignature:
            return False


def validate_reviewer_key_binding(
    artifact: dict[str, Any],
    signer: Signer,
    *,
    reviewer_id: str | None = None,
    key_registry: dict[str, str] | None = None,
) -> None:
    """Ensure signer public key matches reviewer fixture or registry."""
    signer_ref = signer.public_key_ref()
    reviewer = artifact.get("reviewer") or {}
    declared_ref = reviewer.get("reviewer_public_key_ref") or artifact.get(
        "reviewer_public_key_ref"
    )
    if declared_ref and declared_ref != signer_ref:
        raise ScopeValidationError(
            f"Signer public key ref {signer_ref} does not match reviewer fixture {declared_ref}"
        )
    rid = reviewer_id or reviewer.get("reviewer_id")
    if key_registry and rid and rid in key_registry:
        expected = key_registry[rid]
        if expected != signer_ref:
            raise ScopeValidationError(
                f"Signer public key ref {signer_ref} does not match registry for {rid}"
            )


def attach_signature(
    artifact: dict[str, Any],
    signer: Signer,
    *,
    hash_field: str,
    signature_field: str,
    reviewer_id: str | None = None,
    key_registry: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Attach signature metadata to a decision or grant artifact."""
    validate_reviewer_key_binding(
        artifact, signer, reviewer_id=reviewer_id, key_registry=key_registry
    )
    result = dict(artifact)
    result["reviewer_public_key_ref"] = signer.public_key_ref()
    if "reviewer" in result and isinstance(result["reviewer"], dict):
        result["reviewer"] = dict(result["reviewer"])
        result["reviewer"]["reviewer_public_key_ref"] = signer.public_key_ref()
    result["signature_algorithm"] = Ed25519Signer.ALGORITHM
    result["signed_payload_hash"] = artifact[hash_field]
    result[signature_field] = signer.sign(artifact, hash_field)
    return result


def verify_artifact_signature(
    artifact: dict[str, Any],
    verifier: Signer | Verifier,
    *,
    hash_field: str,
    signature_field: str,
) -> bool:
    sig = artifact.get(signature_field)
    key_ref = artifact.get("reviewer_public_key_ref")
    if not sig or not key_ref:
        return False
    if artifact.get("signed_payload_hash") != artifact.get(hash_field):
        return False
    return verifier.verify(artifact, hash_field, sig, key_ref)


def validate_signature_required(artifact: dict[str, Any], signature_field: str) -> None:
    from scope.config import require_signatures

    if require_signatures() and not artifact.get(signature_field):
        raise ScopeValidationError(
            f"Production mode requires {signature_field} on artifact"
        )
