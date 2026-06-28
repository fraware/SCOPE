# AKTA Review Output Contract

SCOPE v0.7 freezes the `scope akta review` output contract under `out_dir/`.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Signed or unsigned decision |
| `scope_grant.json` | Issued grant |
| `summary.json` | Adapter summary (validated against schema) |

## summary.json contract

Contract version constant: `scope-akta-review-v0.7` (`scope.integration_versions.AKTA_REVIEW_CONTRACT_VERSION`).

Required fields:

```json
{
  "packet_path": "...",
  "decision_path": "...",
  "grant_path": "...",
  "approved_scope": "...",
  "requested_scope": "...",
  "adapter_contract_version": "scope-akta-review-v0.7",
  "identity_assurance_level": "IAL0",
  "signing_assurance_level": "SAL1",
  "production_mode": false
}
```

Optional fields: `status`, `packet_id`, `decision_id`, `grant_id`, `allowed_tools`, `blocked_tools`, `decision_type`, `scope_trust_root_hash`, `queue_id`.

Schema: `schemas/scope_akta_review_summary.schema.json`

## Acceptance criteria

`scope akta review` enforces:

- Summary validates against schema
- Overbroad approval fails (approved scope stronger than requested)
- Unsigned production grant fails without signing key/provider
- Missing reviewer authority fails (two-stage RBAC + SCOPE policy)

## Primary AKTA path

`scope akta review` is the documented primary AKTA integration path for packet → decision → grant workflows.

## Related documentation

- [akta_integration.md](akta_integration.md) — integration overview
- [akta_scope_demo.md](akta_scope_demo.md) — full cross-repo demo
- [external_integration_contracts.md](external_integration_contracts.md) — AKTA field mappings
