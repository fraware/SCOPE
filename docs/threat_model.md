# Threat Model

## Threats addressed (v0.7)

- Schema validation failures on AKTA imports, packets, decisions, grants, and session artifacts
- Decision tampering (canonical hashes; optional Ed25519 signatures in production mode)
- Grant broadening (scope hierarchy enforcement; overbroad approval rejection)
- Stale approval reuse (expiration checks on protocol version, evidence state, domain overlay, and more)
- Unknown scope / invalid role (fail closed)
- Ledger deletion or tampering (local hash chain verification)
- Fake reviewer identity (partial mitigation via IAL/OIDC/RBAC at IAL3–IAL4; registry key binding at SAL3)
- Unsigned production grants (production mode requires signed decisions; minimum SAL enforced)
- Remote ledger loss (delivery modes: best_effort, at_least_once spool, fail_closed for high-risk grants)
- Queue workflow bypass (explicit 10-state transitions; forbidden direct grant paths)

## Threats partially addressed

- Collusion and institutional pressure (quality metrics detect rubber-stamping; not prevented)
- Artifact substitution without hash verification (packets should use hash-addressed refs; operator responsibility)
- HSM/KMS key exfiltration (SAL4 interface documented; operator-managed external integration)

## Threats not fully addressed

- Reviewer competence, honesty, or scientific judgment
- Domain safety, legal compliance, or physical lab safety
- Live directory sync for enterprise RBAC (YAML-file based only)
- Authoritative remote ledger (local JSONL chain remains source of tamper evidence)

See [trusted_boundary.md](trusted_boundary.md) and [limitations.md](limitations.md).
