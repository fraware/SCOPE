# Registry-signed decision

Scenario: institutional pilot uses `RegistryKeyProvider` with `--reviewer-id` binding to sign a decision via `reviewer_key_registry.yaml`.

## Artifacts

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Registry-signed decision (`decision_signature` present) |
| `scope_grant.json` | Issued grant |
| `summary.json` | Completed AKTA review summary |
| `reviewer_protocol_owner.json` | Reviewer identity (`reviewer_001`) |
| `policy/reviewer_key_registry.yaml` | Registry with `signing_key_path` (pilot only) |
| `reviewer.pem` / `reviewer.pub` | Local Ed25519 keypair (pilot only; do not use in production) |
| `packet_rendered.md` | Markdown packet render |
| `quality_report_snippet.json` | Policy version snippet |

## Regenerate

```bash
scope akta review \
  --akta-trigger examples/protocol_change_review/review_trigger.json \
  --akta-record examples/protocol_change_review/akta_record.json \
  --grant-scope protocol_draft \
  --reviewer examples/protocol_change_review/reviewer_protocol_owner.json \
  --decision-rationale "Registry-signed pilot approval." \
  --signing-provider registry \
  --reviewer-id reviewer_001 \
  --out-dir examples/pilot/registry_signed_decision \
  --policy examples/pilot/registry_signed_decision/policy
```

`--reviewer-id` must match `reviewer.json` `reviewer_id`. Mismatch fails before signing.
