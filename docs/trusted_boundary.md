# Trusted Boundary

SCOPE v0.2 assumes:

- Reviewer identity is provided by a trusted caller or configured registry
- Reviewer role assignments are correctly configured
- Artifacts in packets are authentic or hash-addressed
- Runtime systems enforce grants or pass them to PF-Core
- AKTA Records are valid and schema-checked
- When `SCOPE_PRODUCTION_MODE` is enabled, signing keys are held by authorized reviewers

SCOPE v0.2 does not guarantee reviewer competence, honesty, scientific truth, domain safety, legal compliance, or physical lab safety.

## Production mode and signing

Set `SCOPE_PRODUCTION_MODE=true` (or `1`, `yes`, `production`) to enforce fail-closed signing rules:

| Stage | Requirement |
|-------|-------------|
| Decision submit | Decision input must include `decision_signature` (or be signed before submit) |
| Grant issue | Source decision must carry a valid `decision_signature` |
| Grant sign | Optional; copies signature metadata from decision when present |

Grant issue validates the **decision** signature, not the grant signature. Grant signing is a separate step for downstream verification, PF/PCS export, and institutional audit trails.

```bash
scope decision sign --decision decision.json --key reviewer.pem --out signed_decision.json
scope grant issue --packet packet.json --decision signed_decision.json --out grant.json
scope grant sign --grant grant.json --key reviewer.pem --out signed_grant.json  # optional
scope verify --artifact signed_decision.json --key reviewer.pem --type decision
```

REST sign/verify endpoints require `SCOPE_SIGNING_KEY` or an explicit `key_path` in the request body.

## Multi-reviewer sessions

Review sessions collect votes from required roles before grant issuance. Safety officers listed in `safety_veto_roles` may submit a `reject` decision even when not in the action's required role list; a safety veto blocks grant issuance regardless of approving votes.

Session state is held in memory on the REST server singleton. CLI workflows persist session artifacts to disk via `scope review session` commands.

## Policy version

Active policy is tagged `scope-core-v0.2`. Grants record `provenance.scope_policy_version`; runtime context may include matching `scope_policy_version` for expiration checks.
