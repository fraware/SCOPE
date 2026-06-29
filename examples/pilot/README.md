# SCOPE Pilot Fixture Pack (v1.0.0)

Institutional pilot scenarios generated with SCOPE v1.0.0 CLI and engine APIs. Each subdirectory is self-contained with review artifacts, queue state where applicable, rendered packet markdown, and a quality report snippet.

| Scenario | Directory | Highlights |
|----------|-----------|------------|
| Single-reviewer protocol draft | [single_reviewer_protocol_draft](single_reviewer_protocol_draft/) | One-shot `scope akta review` |
| Multi-role genomics co-review | [multi_role_genomics_review](multi_role_genomics_review/) | `--session-complete` issues grant from votes |
| Expired queue reopen | [expired_queue_reopen](expired_queue_reopen/) | Queue `expired` then `reopen` |
| Needs information flow | [needs_information_flow](needs_information_flow/) | `needs_information` to `in_review` |
| Registry-signed decision | [registry_signed_decision](registry_signed_decision/) | `--signing-provider registry --reviewer-id` |

Policy bundle: `scope-core-v1.0`. AKTA review contract: `scope-akta-review-v1.0`.

Each scenario includes `manifest.json` (artifact inventory and schema versions) and `expected_verification.json` (checksums, status values, queue states). Verify offline:

```bash
python scripts/verify_pilot_fixtures.py
python scripts/verify_ledger_chain.py .scope/ledger.jsonl
```
