# Key Management (v0.7)

SCOPE supports optional local binding between `reviewer_id` and Ed25519 public keys via `policy/reviewer_key_registry.yaml`.

See also [signing_assurance.md](signing_assurance.md) and [trusted_boundary.md](trusted_boundary.md).

## Signing providers

| Provider | CLI flag | SAL level | Description |
|----------|----------|-----------|-------------|
| `local` | `--signing-key` / `--key` | SAL1 | Explicit Ed25519 private key PEM (default) |
| `env` | `--signing-provider env` | SAL2 | Reads `SCOPE_SIGNING_KEY` path |
| `registry` | `--signing-provider registry --reviewer-id X` | SAL3 | Pilot: `signing_key_path` in registry entry |

```bash
scope decision sign --decision d.json --signing-provider env --out signed.json
scope akta review ... --signing-provider registry --reviewer-id ds1
```

**Pilot only:** `signing_key_path` in `reviewer_key_registry.yaml` references a local private key for institutional pilots. Do not use in production; prefer HSM or env-scoped keys.

Production mode enforces minimum SAL per scope via `policy/minimum_signing_assurance.yaml` (default SAL1; high-risk scopes such as `robot_queue_submission` require SAL3).

## Registry file

```yaml
version: scope-core-v0.7
reviewers:
  protocol_owner_1:
    public_key_ref: sha256:...
    public_key_file: .scope/keys/protocol_owner_1.pub
```

- `public_key_ref` is the SHA-256 canonical hash of the PEM public key (same value attached to signed decisions).
- `public_key_file` enables signature verification without passing `--public-key` on the CLI.
- Private keys remain local to reviewers and are never stored in the registry.

## Register a reviewer key

```bash
scope key register --reviewer-id protocol_owner_1 \
  --public-key keys/protocol_owner.pub \
  --policy policy/
```

This updates `policy/reviewer_key_registry.yaml` and prints the computed `public_key_ref`.

## Migrate legacy registry entries

If an older registry YAML contains `private_key_file` or `private_key_path`, remove them:

```bash
scope key migrate-registry --policy policy/
```

Private keys are stripped on registry load and register as well; migration rewrites the YAML on disk.

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
- `scope_trust_root_hash` (combined policy + registry trust root)

## Trust root hashes

Three related digests appear in decision and grant provenance:

| Field | Meaning |
|-------|---------|
| `scope_policy_hash` | SHA-256 of canonical policy YAML bundle (roles, scopes, matrices, overlays) |
| `reviewer_key_registry_hash` | SHA-256 of canonical `reviewer_key_registry.yaml` |
| `scope_trust_root_hash` | SHA-256 of concatenated `scope_policy_hash` + `reviewer_key_registry_hash` |

Use `scope_trust_root_hash` when a downstream system needs a single digest binding both authorization policy and reviewer identity policy. Policy and registry hashes remain available separately for partial updates or audit.

## Operational guidance

- Treat the registry as institution-local policy, version-controlled separately from reviewer PEM files.
- Rotate keys by registering a new public key ref, re-signing outstanding decisions if needed, and bumping registry version.
- Production deployments should store private keys in an HSM or institutional secret store. SCOPE v0.7 records signing assurance level (SAL) on provenance; wire external HSM/KMS via `HsmKmsSigningProvider` (SAL4 interface only).
