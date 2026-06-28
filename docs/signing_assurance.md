# Signing Assurance (SAL)

SCOPE v0.7 records signing assurance levels on decision and grant provenance.

## Levels

| Level | Meaning |
|-------|---------|
| SAL0 | Unsigned artifact |
| SAL1 | Local PEM (`LocalPemProvider`) with valid Ed25519 signature |
| SAL2 | `EnvKeyProvider` (environment key path) |
| SAL3 | `RegistryKeyProvider` with reviewer_id binding |
| SAL4 | External HSM/KMS (interface only; no in-repo implementation) |

## Policy

`policy/minimum_signing_assurance.yaml` defines production minimums:

- Default minimum: SAL1
- High-risk scopes (e.g. `robot_queue_submission`): SAL3

Production mode enforces minimum SAL at grant issue.

## Operational risk

`EnvKeyProvider` emits CLI and log warnings about environment key path exposure. Prefer registry-bound (SAL3) or HSM/KMS (SAL4) for production.

## SAL4 external boundary

`scope.signing_assurance.HsmKmsSigningProvider` documents the institutional integration point. Configure vendor SDKs outside SCOPE; set `SCOPE_HSM_ENDPOINT` when wiring external signers.

Schema provenance field: `signing_assurance_level`.
