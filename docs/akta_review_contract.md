# AKTA Review Output Contract

SCOPE v0.8.1 splits the `scope akta review` output contract by `summary.status`.

## Branching rule

Consumers **must** branch on `summary.status`:

| `summary.status` | Schema | Artifacts |
|------------------|--------|-----------|
| `completed` | `schemas/scope_akta_review_summary.schema.json` | packet, decision, grant, summary |
| `session_required` | `schemas/scope_akta_review_session_summary.schema.json` | packet, summary only |

The two schemas are mutually exclusive: completed summaries cannot carry session fields (`session_id`, `required_roles`, `message`); session summaries cannot carry grant/decision fields (`decision_path`, `grant_path`, `approved_scope`, IAL/SAL, etc.).

Contract version constant: `scope-akta-review-v0.8.1` (`scope.integration_versions.AKTA_REVIEW_CONTRACT_VERSION`).

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Signed or unsigned decision (`completed` only) |
| `scope_grant.json` | Issued grant (`completed` only) |
| `summary.json` | Adapter summary (schema selected by `status`) |

## summary.json contract (completed review)

Required fields:

```json
{
  "status": "completed",
  "packet_path": "...",
  "decision_path": "...",
  "grant_path": "...",
  "approved_scope": "...",
  "requested_scope": "...",
  "adapter_contract_version": "scope-akta-review-v0.8.1",
  "identity_assurance_level": "IAL0",
  "signing_assurance_level": "SAL1",
  "production_mode": false
}
```

Optional fields: `packet_id`, `decision_id`, `grant_id`, `allowed_tools`, `blocked_tools`, `decision_type`, `scope_trust_root_hash`, `queue_id`.

Schema: `schemas/scope_akta_review_summary.schema.json`

## summary.json contract (session mode)

When multi-role review is required and `--session` is passed, `run_akta_review` creates a review session and writes a session summary instead of decision/grant artifacts.

Required fields:

```json
{
  "status": "session_required",
  "packet_id": "SCOPE-PKT-...",
  "session_id": "SCOPE-SESS-...",
  "required_roles": ["domain_scientist", "protocol_owner"],
  "message": "Multi-role review session created; submit votes before grant issue.",
  "adapter_contract_version": "scope-akta-review-v0.8.1",
  "production_mode": false
}
```

Optional fields: `requested_scope`, `packet_path`.

Schema: `schemas/scope_akta_review_session_summary.schema.json`

Without `--session`, multi-role packets fail with an explicit error directing operators to re-run with `--session` or use `scope review session create`.

Runtime validation: `scope.akta_review.validate_summary_artifact(summary)` selects the schema from `summary.status`.

## Session grant provenance

When a grant is issued from a multi-reviewer session (`issue_grant_from_session`), provenance includes aggregated session fields:

| Field | Description |
|-------|-------------|
| `contributing_identity_assurance_levels` | Per-decision IAL with reviewer ID and role |
| `contributing_authority_checks` | Per-decision `authority_checks` blocks |
| `minimum_identity_assurance_level` | Weakest IAL across contributing decisions |
| `minimum_signing_assurance_level` | Weakest SAL across contributing decisions |
| `veto_roles_applied` | Safety veto roles from quorum policy |
| `quorum_policy_hash` | Digest of session quorum policy |

When `contributing_identity_assurance_levels` is present, `schemas/scope_grant.schema.json` requires all session provenance fields. Single-reviewer grants omit them entirely.

Runtime double-check: `scope.session_provenance.validate_session_grant_provenance`.

## Reviewer ID binding

All entry points (CLI, REST, Python API) call `scope.akta_review.resolve_reviewer_id()` before signing:

- When `--signing-provider registry` is used, pass `--reviewer-id` to bind the registry lookup.
- If provided, it must match `reviewer.json` `reviewer_id`; mismatch fails before signing.
- Registry signing cannot proceed without an explicit, validated reviewer identity.

## Acceptance criteria

`scope akta review` enforces:

- Summary validates against the schema for its `status` branch
- Completed and session summaries cannot be confused
- Overbroad approval fails (approved scope stronger than requested)
- Unsigned production grant fails without signing key/provider
- Missing reviewer authority fails (two-stage RBAC + SCOPE policy)
- Multi-role packets without `--session` fail with session guidance

## Primary AKTA path

`scope akta review` is the documented primary AKTA integration path for packet → decision → grant workflows.

## Related documentation

- [akta_integration.md](akta_integration.md) — integration overview
- [akta_scope_demo.md](akta_scope_demo.md) — full cross-repo demo
- [external_integration_contracts.md](external_integration_contracts.md) — AKTA field mappings
- [key_management.md](key_management.md) — registry signing and `--reviewer-id`
