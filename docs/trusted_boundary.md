# Trusted Boundary

SCOPE v0.8 assumes:

- Reviewer identity is provided by a trusted caller, OIDC/JWT verification, or configured registry
- Reviewer role assignments are correctly configured in policy YAML and, when enabled, `org_rbac.yaml`
- Artifacts in packets are authentic or hash-addressed
- Runtime systems enforce grants or pass them to PF-Core
- AKTA Records are valid and schema-checked
- When `SCOPE_PRODUCTION_MODE` is enabled, signing keys are held by authorized reviewers and meet minimum signing assurance (SAL) for the approved scope
- Session stores (JSON/SQLite) are protected at the filesystem level
- Ledger delivery mode matches institutional risk tolerance (`SCOPE_LEDGER_DELIVERY_MODE`)

SCOPE v0.8 does not guarantee reviewer competence, honesty, scientific truth, domain safety, legal compliance, or physical lab safety.

## Production mode and signing

Set `SCOPE_PRODUCTION_MODE=true` (or `1`, `yes`, `production`) to enforce fail-closed signing at grant issue:

| Stage | Requirement |
|-------|-------------|
| Decision submit | Signature optional; unsigned decisions marked `signature_required=true` |
| Decision validate | Use `--require-signature` to enforce signature presence |
| Grant issue | Source decision must carry a valid `decision_signature`; minimum SAL enforced per scope |
| Grant sign | Optional; copies signature metadata from decision when present |
| Verify | Use `--public-key` for verification without private key access |

Recommended production workflow:

```bash
scope decision submit --packet packet.json --reviewer reviewer.json \
  --decision decision.json --out decision.json
scope decision sign --decision decision.json --key reviewer.pem --out signed_decision.json
scope grant issue --packet packet.json --decision signed_decision.json --out grant.json
scope verify --artifact signed_decision.json --public-key reviewer.pub --type decision
```

Grant issue validates the **decision** signature, not the grant signature. Grant signing is a separate step for downstream verification, PF/PCS export, and institutional audit trails.

Signing assurance levels (SAL0–SAL4) are recorded on grant provenance. See [signing_assurance.md](signing_assurance.md) and [key_management.md](key_management.md).

REST sign/verify endpoints accept `SCOPE_SIGNING_KEY` (private) or `public_key_path` in verify requests.

## Identity assurance (IAL)

Identity assurance levels (IAL0–IAL4) record how reviewer identity was established. Caller JSON alone is IAL0; OIDC plus org RBAC can reach IAL3/IAL4. Two-stage authority checks (`authority_checks` provenance) distinguish skipped RBAC from failed checks.

| Variable | Purpose |
|----------|---------|
| `SCOPE_OIDC_ENABLED` | Enable REST middleware identity binding |
| `SCOPE_OIDC_JWKS_URL` | JWKS endpoint for RS256 verification |
| `SCOPE_OIDC_ISSUER` | Expected JWT `iss` claim |
| `SCOPE_OIDC_AUDIENCE` | Expected JWT `aud` claim |
| `SCOPE_OIDC_PUBLIC_KEY_PEM` | Static PEM alternative to JWKS |
| `SCOPE_ENFORCE_RBAC` | Require org RBAC on decision submit (also triggered at IAL3/IAL4) |

Claim mapping is configured in `policy/identity_mapping.yaml`. CLI: `scope identity verify-token --token ...`

See [identity_assurance.md](identity_assurance.md) and [rbac_scope_authority.md](rbac_scope_authority.md).

## Ledger delivery

Remote ledger append supports three delivery modes via `SCOPE_LEDGER_DELIVERY_MODE`:

| Mode | Behavior |
|------|----------|
| `best_effort` | Append to remote sink without blocking grant issue (default) |
| `at_least_once` | Spool failed remote deliveries for retry |
| `fail_closed` | Block high-risk grant issuance when remote delivery fails |

Authoritative tamper evidence remains the local hash-chained JSONL ledger. See [limitations.md](limitations.md).

## Multi-reviewer sessions

Review sessions collect votes from required roles before grant issuance. Safety officers listed in `safety_veto_roles` may submit a `reject` decision even when not in the action's required role list; a safety veto blocks grant issuance regardless of approving votes.

Session persistence is configurable:

| Backend | CLI | Environment |
|---------|-----|-------------|
| memory | `--session-store memory` (default) | `SCOPE_SESSION_STORE=memory` |
| JSON files | `--session-store json --session-dir .scope/sessions` | `SCOPE_SESSION_STORE=json` |
| SQLite | `--session-store sqlite --session-dir .scope/sessions.db` | `SCOPE_SESSION_STORE=sqlite` |

Duplicate votes from the same reviewer are rejected. Votes are recorded in both the ledger and the session store.

## Policy version

Active policy is tagged `scope-core-v0.8`. Grants record `provenance.scope_policy_version`; runtime context may include matching `scope_policy_version` for expiration checks.

Session grants additionally record aggregated provenance: `contributing_identity_assurance_levels`, `contributing_authority_checks`, `minimum_identity_assurance_level`, `minimum_signing_assurance_level`, `veto_roles_applied`, and `quorum_policy_hash`. See [akta_review_contract.md](akta_review_contract.md).

## Trust root

Signed decisions and grants carry provenance hashes:

- `scope_policy_hash` — canonical digest of the policy bundle
- `reviewer_key_registry_hash` — digest of `reviewer_key_registry.yaml`
- `scope_trust_root_hash` — SHA-256 of the concatenated policy and registry hashes

PCS release manifests include `scope_trust_root_hash` for downstream verification. See [key_management.md](key_management.md) for registry workflow.
