# Reviewer Guide

## What you receive

A SCOPE Packet includes:

- AI output summary and references
- Requested action and tool
- AKTA classification and admissibility
- Evidence state and validation status
- Blocked tools and allowed next steps
- Permitted decision options

## Decision types

- `approve` / `approve_narrower_scope` — emit a bounded grant
- `reject` — keep AKTA blocks active
- `request_more_evidence` — remain in review state
- `abstain_conflict_or_insufficient_expertise` — escalate or reassign

## Choosing scope

Select the weakest scope that matches the evidence. Approving a stronger scope than necessary triggers quality warnings and may be rejected by policy.

## Co-review

Some action types (e.g. publication claim escalation) require co-review from multiple roles. Include `co_reviewers` in your decision when domain and publication reviewers must both sign off.
