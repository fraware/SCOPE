# RBAC vs SCOPE Authority Separation

SCOPE v0.7 enforces two-stage authority before accepting decisions.

## Stage 1: Institutional RBAC

Maps `reviewer_id` to effective institutional roles from `policy/org_rbac.yaml`:

- Direct membership in `org_units`
- Active delegations (with expiry check)
- RBAC action permissions (`can_submit_decisions`, `can_vote_in_session`)

Institutional RBAC is separate from SCOPE scope permissions.

## Stage 2: SCOPE Policy

Maps effective role to scientific action and approval scope via `policy/reviewer_roles.yaml`:

- `role_to_action_matrix.yaml` — which roles may act on action types
- `can_approve_scopes` — which scopes each SCOPE role may approve

A reviewer may hold an institutional role that does not permit a given SCOPE scope even when RBAC grants directory membership.

## Examples

- `domain_scientist` in org directory cannot approve `robot_queue_submission` when SCOPE role policy forbids it.
- `protocol_owner` cannot approve `robot_queue_submission` unless listed in `can_approve_scopes`.
- Expired delegation invalidates institutional authority for the delegated role.

## Enforcement

Implemented in `scope/authority.py` and invoked from `ScopeEngine.submit_decision` and session votes when:

- `SCOPE_ENFORCE_RBAC=1`, or
- Identity assurance reaches IAL3/IAL4 (institutional OIDC path)

Identity assurance provenance records which stage resolved the role (`role_resolution_source`).

## authority_checks provenance

Every decision and grant records explicit two-stage authority outcomes:

```json
{
  "authority_checks": {
    "rbac_enforced": true,
    "rbac_role_valid": true,
    "scope_role_valid": true,
    "scope_approval_valid": true,
    "delegation_id": null
  }
}
```

When RBAC is disabled or identity is below IAL3, `rbac_enforced` and `rbac_role_valid` are `false` so auditors can distinguish skipped checks from passed checks. Active delegations populate `delegation_id` in both identity provenance and `authority_checks`.

## Related documentation

- [identity_assurance.md](identity_assurance.md) — IAL levels and provenance fields
- [limitations.md](limitations.md) — RBAC scope and external IdP boundaries
- [institutional_pilot_guide.md](institutional_pilot_guide.md) — pilot RBAC configuration
