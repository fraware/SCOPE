"""JWT test helpers for OIDC identity verification."""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_rsa_keypair() -> tuple[Any, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_pem


def build_rs256_jwt(
    private_key: Any,
    claims: dict[str, Any],
    *,
    kid: str = "test-kid",
) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    header_b64 = _b64url(json.dumps(header, sort_keys=True).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(claims, sort_keys=True).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = _b64url(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"
