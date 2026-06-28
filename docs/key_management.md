# Key management (v0.5)

SCOPE supports optional local binding between `reviewer_id` and Ed25519 public keys via `policy/reviewer_key_registry.yaml`.

## Registry file

```yaml
version: scope-core-v0.5
reviewers:
  protocol_owner_1:
    public_key_ref: sha256:...
    public_key_file: .scope/keys/protocol_owner_1.pub
    private_key_file: .scope/keys/protocol_owner_1.pem  # dev only; omit in production
```

- `public_key_ref` is the SHA-256 canonical hash of the PEM public key (same value attached to signed decisions).
- `public_key_file` enables signature verification without passing `--public-key` on the CLI.
- `private_key_file` is stored only for development convenience; never commit production private keys.

## Register a reviewer key

```bash
scope key register --reviewer-id protocol_owner_1 \
  --public-key keys/protocol_owner.pub \
  --private-key keys/protocol_owner.pem \
  --policy policy/
```

This updates `policy/reviewer_key_registry.yaml` and prints the computed `public_key_ref`.

## Signing enforcement

When a reviewer ID has a registry entry, `scope decision sign` and engine signing fail if the signer public key does not match the registered ref (even when the decision artifact omits an explicit ref).

Decisions should carry `reviewer.reviewer_public_key_ref` matching the registry after signing.

## Verify against registry

```bash
scope key verify-registry --decision signed_decision.json --policy policy/
```

Checks:

1. `reviewer.reviewer_id` exists in the registry
2. `reviewer_public_key_ref` on the decision matches the registry entry
3. When `public_key_file` is configured and the decision is signed, verifies the Ed25519 signature

No manual `--public-key` is required when `public_key_file` is present in the registry.

## PCS export metadata

PCS release manifests include:

- `reviewer_public_key_ref` (from signed decision when present)
- `registry_version` (registry YAML `version` field)
- `registry_hash` (SHA-256 of canonical registry YAML)

## Operational guidance

- Treat the registry as institution-local policy, version-controlled separately from reviewer PEM files.
- Rotate keys by registering a new public key ref, re-signing outstanding decisions if needed, and bumping registry version.
- Production deployments should store private keys in an HSM or institutional secret store; SCOPE v0.5 still signs locally via PEM paths only.
