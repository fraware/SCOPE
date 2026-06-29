# SCOPE Review Packet

*This display is for review coordination only. It does not constitute certification, legal authorization, or institutional approval.*

## Identification

- Packet ID: SCOPE-PKT-42A16F
- AKTA Record: AKTA-SAR-S03
- Created: 2026-06-29T09:19:52Z

## Requested Action

- Action: plan_validation_experiment
- Tool: experiment_planner.create_validation_plan
- Action type: A6_experimental_planning
- Requested scope: single_validation_run_draft
- Review route: none
- Scope inference source: tool_registry
- Admissibility: review_required

## Required Reviewers

- Roles: domain_scientist, protocol_owner

## Scientific Context

- Domain: materials
- Evidence state: E1_weak_signal
- Validation status: V0_unvalidated
- Verification status: unknown
- Protocol version: protocol_v2

## Blocked Tools (severity)

- robot_queue.submit (high severity — operational or escalation risk)

## AKTA Constraints

- Blocked tools: robot_queue.submit
- Allowed next steps: approve validation draft only, request additional evidence, reject experimental plan

## Approval Scope Context

- single_validation_run_draft: One validation run draft.

## Approval Permits

- experiment_planner.create_validation_plan
- protocol_editor.draft_change

## Approval Does NOT Permit

- protocol_editor.update_active_protocol
- lab_scheduler.prioritize
- robot_queue.submit

## Decision Options

- Allowed: approve, approve_narrower_scope, reject, request_more_evidence, abstain_conflict_or_insufficient_expertise

## Reviewer Checklist

- Confirm your role is one of: domain_scientist, protocol_owner
- Verify requested action and tool match the scientific context
- Select the weakest approval scope supported by evidence
- Document rationale for approve, reject, or request-more-evidence
- Declare conflicts of interest before submitting a decision
- Allowed decision types: approve, approve_narrower_scope, reject, request_more_evidence, abstain_conflict_or_insufficient_expertise


---

This display is for review coordination only. It does not constitute certification, legal authorization, or institutional approval.
