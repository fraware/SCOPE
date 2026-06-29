# AKTA to SCOPE to PF to PCS Demo

This document walks through the full authorization chain using SCOPE v0.7.

Related: [akta_review_contract.md](akta_review_contract.md), [external_integration_contracts.md](external_integration_contracts.md), [institutional_pilot_guide.md](institutional_pilot_guide.md).

## Primary path: `scope akta review`

For the common case (single reviewer, approval at a declared scope), use the one-shot command:

```powershell
scope akta review `
  --akta-record examples/protocol_drift/akta_record.json `
  --akta-trigger examples/protocol_drift/review_trigger.json `
  --grant-scope protocol_draft `
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json `
  --decision-rationale "Narrow protocol draft approval only." `
  --out-dir /tmp/akta_review_out
```

Outputs in `/tmp/akta_review_out/`:

| File | Description |
|------|-------------|
| `scope_review_packet.json` | SCOPE review packet from AKTA inputs |
| `scope_decision.json` | Scoped approval decision |
| `scope_grant.json` | Bounded authorization grant |
| `summary.json` | Machine-readable contract summary (validated against schema) |

`summary.json` includes `adapter_contract_version` (`scope-akta-review-v0.8.1`), branches on `status` (`completed` or `session_required`), and records `identity_assurance_level`, `signing_assurance_level`, and `production_mode` on completed summaries.

SCOPE rejects overbroad `--grant-scope` values against the packet's `requested_scope`.

In production mode (`$env:SCOPE_PRODUCTION_MODE = "true"`), pass `--signing-key` or `--signing-provider` with the reviewer's key. The command signs the decision before grant issue:

```powershell
$env:SCOPE_PRODUCTION_MODE = "true"
scope akta review `
  --akta-record examples/protocol_drift/akta_record.json `
  --akta-trigger examples/protocol_drift/review_trigger.json `
  --grant-scope protocol_draft `
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json `
  --decision-rationale "Narrow protocol draft approval only." `
  --signing-key keys/reviewer.pem `
  --out-dir /tmp/akta_review_out
```

Optional institutional identity:

```powershell
scope akta review ... `
  --identity-token $env:OIDC_TOKEN `
  --enforce-rbac `
  --signing-provider registry --reviewer-id protocol_owner_1
```

Without signing credentials in production mode, the command fails before writing a grant.

For non-production workflows, sign the decision and re-issue the grant from saved artifacts (see Step 4 below).

## Step-by-step workflow (advanced)

Use individual CLI commands when you need VSA reports, multi-step review, or custom decision payloads.

## Prerequisites

```powershell
pip install -e ".[dev]"
```

## Step 1: AKTA produces review trigger

AKTA (separate repository) evaluates a scientific action and emits:

- An **AKTA Record** with nested `requested_transition`, `classification`, and `decision`
- A **Review Trigger** when admissibility is `review_required` or `authorization_required`

Example nested record: `examples/protocol_drift/akta_record.json`

Example trigger with explicit scope: `examples/protocol_drift/review_trigger.json`

## Step 2: SCOPE creates review packet

```powershell
scope packet create `
  --akta-record examples/protocol_drift/akta_record.json `
  --akta-trigger examples/protocol_drift/review_trigger.json `
  --out /tmp/scope_packet.json
```

The packet includes:

- `review_request.requested_scope` from AKTA trigger (valid approval scope names only)
- `review_request.review_route` from AKTA `review_scope` (may be a non-scope route label)
- `review_request.scope_inference_source` (`akta_trigger`, `tool_registry`, or `unknown`)
- Required reviewer roles from policy matrix
- AKTA constraints (blocked tools, allowed next steps)

Render for reviewers:

```powershell
scope packet render /tmp/scope_packet.json --format markdown
```

## Step 3: Reviewer submits decision

```powershell
scope decision submit `
  --packet /tmp/scope_packet.json `
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json `
  --decision examples/protocol_drift/decision.json `
  --out /tmp/scope_decision.json
```

SCOPE rejects overbroad approvals against explicit `requested_scope`.

For multi-reviewer actions (e.g. A6), use review sessions with persistent storage:

```powershell
scope review session create --packet /tmp/scope_packet.json --out /tmp/session.json `
  --session-store json --session-dir /tmp/sessions

scope review session vote --session /tmp/session.json --packet /tmp/scope_packet.json `
  --reviewer examples/protocol_drift/reviewer_protocol_owner.json `
  --decision examples/protocol_drift/decision.json --out /tmp/decision_po.json `
  --session-store json --session-dir /tmp/sessions

scope review session status --session-id SCOPE-SESS-XXXXXX --packet /tmp/scope_packet.json `
  --session-store json --session-dir /tmp/sessions
```

Quorum modes (`require_all`, `require_any`, `n_of_m`, `statistical_co_review`) and
`safety_veto_roles` are set via optional `--quorum-policy` on session create.

## Step 4: Issue grant

Production mode (`$env:SCOPE_PRODUCTION_MODE = "true"`) requires a signed **decision**
before grant issue. Submit unsigned, sign, then issue:

```powershell
scope grant issue `
  --packet /tmp/scope_packet.json `
  --decision /tmp/scope_decision.json `
  --out /tmp/scope_grant.json
```

Signing workflow (decision required in production mode; grant signing optional):

```powershell
scope decision submit ... --out /tmp/scope_decision.json
scope decision sign --decision /tmp/scope_decision.json --key keys/reviewer.pem --out /tmp/signed_decision.json
scope decision validate --require-signature /tmp/signed_decision.json
scope grant issue --packet /tmp/scope_packet.json --decision /tmp/signed_decision.json --out /tmp/scope_grant.json
scope grant sign --grant /tmp/scope_grant.json --key keys/reviewer.pem --out /tmp/signed_grant.json
scope verify --artifact /tmp/signed_decision.json --public-key keys/reviewer.pub --type decision
```

## Step 5: Runtime enforcement

```powershell
scope grant check `
  --grant /tmp/scope_grant.json `
  --requested-tool protocol_editor.draft_change `
  --context examples/protocol_drift/current_context.json `
  --ledger /tmp/scope_events.jsonl
```

Ledger records `grant_used`. Single-use grants block second use. Revocation:

```powershell
scope grant revoke --grant-id SCOPE-GRANT-XXXXXX --ledger /tmp/scope_events.jsonl
scope grant status --grant-id SCOPE-GRANT-XXXXXX --ledger /tmp/scope_events.jsonl
```

## Step 6: Export to PF-Core and PCS

```powershell
scope export pf --grant /tmp/scope_grant.json --out /tmp/pf_obligation.json --validate
scope export pcs `
  --packet /tmp/scope_packet.json `
  --decision /tmp/scope_decision.json `
  --grant /tmp/scope_grant.json `
  --out /tmp/pcs_bundle `
  --validate
```

PCS bundle includes manifest hashes for tamper detection. Obligation version: `pf-core-v0.5`; manifest version: `pcs-v0.5`.

## Step 7: Quality report

```powershell
scope quality report --ledger /tmp/scope_events.jsonl --out /tmp/quality_report.json `
  --queue-dir .scope/queues
```

Report sections: summary, by_reviewer, by_role, by_action_type, warnings.

## AKTA CLI (reference)

When AKTA is installed separately:

```bash
akta record evaluate --input action.json --out akta_record.json
akta review trigger --record akta_record.json --out review_trigger.json
```

SCOPE consumes both artifacts via `scope packet create` or the one-shot `scope akta review`.
