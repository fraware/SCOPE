# Review Doctrine

## Principles

1. **Review is not approval** — reviewers may approve, reject, narrow, request evidence, escalate, or abstain.
2. **Approval is never global** — every approval specifies an exact scope.
3. **Weaker scope never implies stronger scope** — protocol draft does not authorize active protocol update.
4. **Expiration is mandatory** — every grant expires by time, event, version, use, or revocation.
5. **Review must be measurable** — SCOPE detects rubber-stamping, stale grants, and overbroad approvals.
6. **Human judgment must become machine-readable** — runtime can enforce decisions; release systems can audit them.
7. **SCOPE does not certify safety** — grants authorize scoped transitions, not scientific correctness.

See [scoped_scientific_authorization.md](scoped_scientific_authorization.md) and [limitations.md](limitations.md).

## Packet design

Packets must not ask "Do you approve this?" They ask whether the reviewer approves a specific action under a specific scope with named blocked tools and expiration conditions.
