# Trusted Boundary

SCOPE v0.3 assumes:

- Reviewer identity is provided by a trusted caller or configured registry
- Reviewer role assignments are correctly configured in policy YAML
- Artifacts in packets are authentic or hash-addressed
- Runtime systems enforce grants or pass them to PF-Core
- AKTA Records are valid and schema-checked
- When `SCOPE_PRODUCTION_MODE` is enabled, signing keys are held by authorized reviewers
- Session stores (JSON/SQLite) are protected at the filesystem level

SCOPE v0.3 does not guarantee reviewer competence, honesty, scientific truth, domain safety, legal compliance, or physical lab safety.

## Production mode and signing

Set `SCOPE_PRODUCTION_MODE=true` (or `1`, `yes`, `production`) to enforce fail-closed signing at grant issue:

| Stage | Requirement |
|-------|-------------|
| Decision submit | Signature optional; unsigned decisions marked `signature_required=true` |
| Decision validate | Use `--require-signature` to enforce signature presence |
| Grant issue | Source decision must carry a valid `decision_signature` |
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

REST sign/verify endpoints accept `SCOPE_SIGNING_KEY` (private) or `public_key_path` in verify requests.

## Multi-reviewer sessions

Review sessions collect votes from required roles before grant issuance. Safety officers listed in `safety_veto_roles` may submit a `reject` decision even when not in the action's required role list; a safety veto blocks grant issuance regardless of approving votes.

Session persistence is configurable:

| Backend | CLI | Environment |
|---------|-----|---------------|
| memory | `--session-store memory` (default) | `SCOPE_SESSION_STORE=memory` |
| JSON files | `--session-store json --session-dir .scope/sessions` | `SCOPE_SESSION_STORE=json` |
| SQLite | `--session-store sqlite --session-dir .scope/sessions.db` | `SCOPE_SESSION_STORE=sqlite` |

Duplicate votes from the same reviewer are rejected. Votes are recorded in both the ledger and the session store.

## Policy version

Active policy is tagged `scope-core-v0.5`. Grants record `provenance.scope_policy_version`; runtime context may include matching `scope_policy_version` for expiration checks.
