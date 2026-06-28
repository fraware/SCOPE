# Reviewer Guide

## What you receive

A SCOPE Packet includes:

- AI output summary and references
- Requested action, tool, and approval scope
- AKTA `review_route` label (when provided; may be promoted to `requested_scope` when valid)
- AKTA classification and admissibility
- Evidence state and validation status
- Blocked tools with severity indicators
- Permitted decision options
- Optional VSA report summary in `review_artifacts`
- A rendered checklist (via `scope packet render`)

Rendered packets include explicit **Approval Permits** and **Approval Does NOT Permit** sections derived from policy. This display is for review coordination only and does not constitute certification or institutional approval.

## Reviewer roles

### protocol_owner

Responsible for protocol-scoped actions (A5 protocol modification, A6 experimental planning co-review). When reviewing:

- Confirm the requested scope matches the evidence and protocol version
- Prefer `approve_narrower_scope` over broad `approve`
- Block `active_protocol_update` unless validation evidence supports activation
- Co-review with `domain_scientist` on A6 actions before grant issuance

### domain_scientist

Responsible for scientific merit and experimental design (A6 co-review, A4 recommendations). When reviewing:

- Assess evidence state and validation status before approving operational scopes
- Flag weak evidence (`E0_unknown`, `E1_hypothesis`) in rationale
- Approve the weakest scope that matches the scientific claim
- Participate in multi-reviewer sessions where policy requires your role

### biosecurity_reviewer / clinical_reviewer

Domain-specific reviewers with expanded scope permissions. Institutions enable participation via `domain_overlay` policy (see `policy/domain_overlays/`).

## Decision types

- `approve` / `approve_narrower_scope` — emit a bounded grant
- `reject` — keep AKTA blocks active
- `request_more_evidence` — remain in review state
- `abstain_conflict_or_insufficient_expertise` — escalate or reassign

## Choosing scope

Select the weakest scope that matches the evidence. Approving a stronger scope than necessary triggers quality warnings and may be rejected by policy. Compare your approval against `requested_scope` in the packet.

When AKTA sends a valid `review_scope` matching an approval scope name, SCOPE may promote it to `requested_scope` (configurable via `SCOPE_REVIEW_ROUTE_PROMOTION`).

## Multi-reviewer sessions (required for co-review actions)

Action types with `require_all` and multiple roles (A6, A8, A9, A10, `robot_queue_submission`) **require** a review session. Single-decision `co_reviewers` attestation is not supported.

```bash
scope review session create --packet packet.json --out session.json
scope review session vote --session session.json --packet packet.json \
  --reviewer reviewer_a.json --decision decision_a.json --out dec_a.json
scope review session vote --session session.json --packet packet.json \
  --reviewer reviewer_b.json --decision decision_b.json --out dec_b.json
scope review session issue-grant --session session.json --packet packet.json \
  --decision dec_a.json --decision dec_b.json --out grant.json
```

Use `--replace-vote` to supersede a prior vote from the same reviewer.

## Signing

In production mode, submit your decision first, then sign with your Ed25519 private key before grant issue. Your `reviewer_public_key_ref` in the reviewer fixture must match the signing key (or be attached at sign time). Auditors verify with your public key only.

Institutions may configure `policy/reviewer_key_registry.yaml` to bind reviewer IDs to expected public keys.
