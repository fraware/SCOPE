# Protocol Drift Review Example

Demonstrates SCOPE v0.2 handling of protocol modification with explicit `requested_scope`.

AKTA nested record + trigger with `requested_scope: protocol_draft` produces a packet that
restricts approval to draft-level scope. After grant issuance, protocol version drift
invalidates the grant at runtime.

See `docs/akta_scope_demo.md` for the full AKTA to SCOPE to PF to PCS chain.
