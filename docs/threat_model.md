# Threat Model

## v0.1 threats addressed

- Schema validation failures
- Decision tampering (canonical hashes)
- Grant broadening (scope hierarchy enforcement)
- Stale approval reuse (expiration checks)
- Unknown scope / invalid role (fail closed)
- Ledger deletion (hash chain verification)

## v0.1 threats not fully addressed

- Fake reviewer identity (trusted caller assumed)
- Digital signatures and external ledger
- Collusion and institutional pressure
- Artifact substitution without hash verification

See [trusted_boundary.md](trusted_boundary.md) and [limitations.md](limitations.md).
