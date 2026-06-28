# External Integration Contracts (v0.4)

Formal field-mapping contracts for AKTA, PF-Core, PCS, and VSA integrations. These contracts define the shapes SCOPE produces or consumes locally; external repositories must implement compatible endpoints or adapters.

## AKTA import

### Inputs

| Source | Schema | Required fields |
|--------|--------|-----------------|
| AKTA record | `schemas/akta_record_import.schema.json` | `record_id` or nested `classification.scientific_action_type` + `requested_transition.requested_tool` |
| Review trigger | `schemas/akta_review_trigger_import.schema.json` | `scientific_action_type`, `requested_action`, `requested_tool` when record alone is insufficient |

### Scope inference

1. Explicit `requested_scope` on trigger wins (`scope_inference_source: akta_trigger`).
2. Valid `review_scope` / `review_route` promoted when in policy hierarchy (`review_route_promoted`).
3. Otherwise tool registry maps `requested_tool` to scope (`tool_registry`).

### Output (SCOPE packet)

| Packet field | AKTA source |
|--------------|-------------|
| `source.akta_record_id` | `record_id` |
| `source.review_trigger_id` | `trigger_id` |
| `review_request.scientific_action_type` | `scientific_action_type` or `classification.scientific_action_type` |
| `review_request.requested_tool` | `requested_tool` or `requested_transition.requested_tool` |
| `review_request.akta_admissibility` | `akta_admissibility` or `decision.admissibility` |
| `akta_constraints.blocked_tools` | `blocked_tools` or `decision.blocked_tools` |
| `akta_constraints.allowed_next_steps` | `allowed_next_steps` or `decision.next_admissible_steps` |
| `scientific_context.*` | flat fields or `scientific_context` object |

Golden fixture: `adapters/akta/examples/akta_record_nested.json`.

## VSA import

### Input

VSA ScientificReport JSON with:

- `report_id` or `id`
- `evidence_summary.overall_state` or `evidence_summary.evidence_state`
- `claims[]` with optional `status` / `validation_status`
- `validation_results` or `validation` object

### Output (packet `review_artifacts.vsa_report`)

| Field | Description |
|-------|-------------|
| `source` | Always `vsa_scientific_report` |
| `report_id` | VSA report identifier |
| `evidence_summary.overall_state` | Mapped evidence state |
| `claim_warnings[]` | Unsupported or weak claims |
| `validation_results[]` | Normalized validation checks |

Example: `adapters/vsa/examples/scientific_report_example.json`.

## PF-Core export

### Output schema

`schemas/pf_scope_obligation.schema.json` — validated by `adapters/pf_core/export_obligation.py`.

| Field | SCOPE grant source |
|-------|-------------------|
| `obligation_version` | Constant `pf-core-v0.4` |
| `grant_id`, `grant_hash` | Grant artifact |
| `permitted_tools` | `authorization.allowed_tools` |
| `blocked_tools` | `authorization.blocked_tools` |
| `approved_scope` | `authorization.approved_scope` |
| `max_responsibility_level` | `authorization.max_responsibility_level` |
| `constraints.single_use` | `constraints.single_use` |
| `constraints.protocol_version` | `constraints.protocol_version` |
| `constraints.requires_pf_core_trace` | Always `true` |
| `expiration` | Grant `expiration` block |
| `verification_mode` | Always `enforce_at_runtime` |
| Signature fields | Copied when present on signed grant |

Contract fixture: `tests/fixtures/contracts/pf_obligation_contract.json`.

## PCS export

### Output bundle

Directory containing:

- `scope_packet.json`, `scope_decision.json`, `scope_grant.json`, `pf_obligation.json`
- `release_manifest.json` per `schemas/pcs_scope_artifact.schema.json`

| Manifest field | Description |
|----------------|-------------|
| `manifest_version` | `pcs-v0.4` |
| `artifacts` | List of bundled filenames |
| `hashes` | SHA-256 of each artifact (canonical JSON) |
| `source` | `akta_record_id`, `packet_id`, `decision_id`, `grant_id` |
| Optional `ledger_excerpt`, `quality_warnings`, signature fields |

Contract fixture: `tests/fixtures/contracts/pcs_manifest_contract.json`.

## Review assignment

Resolved at packet create via `scope/review_assignment.py`:

| Field | Source |
|-------|--------|
| `action_type` | Packet `scientific_action_type` |
| `required_roles` | Policy matrix + domain overlay |
| `quorum_mode` | `require_all` or `require_any` from matrix |
| `domain_overlay` | Packet scientific context |
| `packet_id` | Packet identifier |

Schema: `schemas/review_assignment.schema.json`.

## Version alignment (v0.4)

| Artifact | Version field | Expected value |
|----------|---------------|----------------|
| SCOPE packet | `packet_version` | `0.4.0` |
| SCOPE grant | `grant_version` | `0.4.0` |
| Quality report | `report_version` | `0.4` |
| PF obligation | `obligation_version` | `pf-core-v0.4` |
| PCS manifest | `manifest_version` | `pcs-v0.4` |
| Policy bundle | `version` in YAML | `scope-core-v0.4` |

## External repo dependencies

These integrations require live services or repositories not present in this repo:

- **AKTA**: authoritative admissibility decisions and nested record storage
- **PF-Core**: runtime obligation enforcement at tool invocation
- **PCS**: release pipeline ingestion and institutional signing workflows
- **VSA**: live ScientificReport generation from validation pipelines

Local adapters validate shapes and hashes; cross-repo end-to-end tests belong in each project's CI once APIs are available.
