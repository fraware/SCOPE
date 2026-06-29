# External Integration Contracts (v0.9)

Formal field-mapping contracts for AKTA, PF-Core, PCS, and VSA integrations. These contracts define the shapes SCOPE produces or consumes locally; external repositories must implement compatible endpoints or adapters.

Related docs: [akta_review_contract.md](akta_review_contract.md), [pf_core_bridge.md](pf_core_bridge.md), [pcs_export.md](pcs_export.md), [evidence_vocab_mapping.md](evidence_vocab_mapping.md).

## AKTA import

### Inputs

| Source | Schema | Required fields |
|--------|--------|-----------------|
| AKTA record | `schemas/akta_record_import.schema.json` | `record_id` or nested `classification.scientific_action_type` + `requested_transition.requested_tool` |
| Review trigger | `schemas/akta_review_trigger_import.schema.json` | `scientific_action_type`, `requested_action`, `requested_tool` when record alone is insufficient |

### AKTA v0.4 trigger aliases

| SCOPE field | AKTA v0.4 source (priority order) |
|-------------|-------------------------------------|
| `akta_admissibility` | `akta_admissibility`, `admissibility` |
| `review_route` | `review_route`, `review_scope` |
| `blocked_tools` | `akta_constraints.blocked_tools`, top-level `blocked_tools` |
| `allowed_next_steps` | `akta_constraints.allowed_next_steps`, top-level `allowed_next_steps` |
| `requested_scope` | top-level `requested_scope` (explicit, wins over route promotion) |

Golden fixtures:

- Record: `adapters/akta/examples/akta_record_nested.json`
- Trigger (v0.4): `adapters/akta/examples/akta_review_trigger_v04.json`

### Scope inference

1. Explicit `requested_scope` on trigger wins (`scope_inference_source: akta_trigger`).
2. Valid `review_route` / `review_scope` promoted when in policy hierarchy (`review_route_promoted`).
3. Otherwise tool registry maps `requested_tool` to scope (`tool_registry`).

### Output (SCOPE packet)

| Packet field | AKTA source |
|--------------|-------------|
| `source.akta_record_id` | `record_id` |
| `source.review_trigger_id` | `trigger_id` |
| `review_request.scientific_action_type` | `scientific_action_type` or `classification.scientific_action_type` |
| `review_request.requested_tool` | `requested_tool` or `requested_transition.requested_tool` |
| `review_request.akta_admissibility` | `akta_admissibility` or `admissibility` or `decision.admissibility` |
| `akta_constraints.blocked_tools` | nested or top-level trigger fields; record `blocked_tools` |
| `akta_constraints.allowed_next_steps` | nested or top-level trigger fields; record steps |
| `scientific_context.*` | flat fields or `scientific_context` object |

Evidence vocabulary mapping: [evidence_vocab_mapping.md](evidence_vocab_mapping.md).

## AKTA review output (primary path)

`scope akta review` and `POST /v0/akta/review` emit a frozen output bundle under `out_dir/`:

| File | Description |
|------|-------------|
| `scope_review_packet.json` | Review packet |
| `scope_decision.json` | Decision (signed in production mode; `completed` only) |
| `scope_grant.json` | Issued grant (`completed` only) |
| `summary.json` | Adapter summary; schema selected by `summary.status` |

Contract version: `scope-akta-review-v0.9` (compatible with v0.8.1+ consumers). Branch on `summary.status`:

| `summary.status` | Schema |
|------------------|--------|
| `completed` | `schemas/scope_akta_review_summary.schema.json` (paths, IAL/SAL, approved scope) |
| `session_required` | `schemas/scope_akta_review_session_summary.schema.json` (session_id, required_roles; no decision/grant artifacts) |

Runtime validation: `scope.akta_review.validate_summary_artifact(summary)`.

Full contract: [akta_review_contract.md](akta_review_contract.md).

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
| `obligation_version` | Constant `pf-core-v0.5` (schema accepts v0.4–v0.5) |
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

See [pf_core_bridge.md](pf_core_bridge.md).

### Live validation (optional)

When `PF_CORE_REPO_PATH` points to a PF-Core checkout, SCOPE can invoke a documented validator script from that repo:

```bash
export PF_CORE_REPO_PATH=/path/to/pf-core
scope export pf --grant grant.json --out pf.json --validate --live
```

Candidate script paths (first match wins):

- `scripts/validate_scope_obligation.py`
- `tools/validate_scope_obligation.py`
- `tests/fixtures/validate_scope_obligation.py`

If the env var is unset or the path is missing, live validation **skips with an explicit message** (default remains local schema validation).

Pytest: `@pytest.mark.live_contract` tests in `tests/test_live_contracts.py`.

## PCS export

### Output bundle

Directory containing:

- `scope_packet.json`, `scope_decision.json`, `scope_grant.json`, `pf_obligation.json`
- `release_manifest.json` per `schemas/pcs_scope_artifact.schema.json`

| Manifest field | Description |
|----------------|-------------|
| `manifest_version` | `pcs-v0.5` (schema accepts v0.4–v0.5) |
| `artifacts` | List of bundled filenames |
| `hashes` | SHA-256 of each artifact (canonical JSON) |
| `source` | `akta_record_id`, `packet_id`, `decision_id`, `grant_id` |
| `reviewer_public_key_ref` | From signed decision when present |
| `registry_version` | `reviewer_key_registry.yaml` version field |
| `registry_hash` | SHA-256 of canonical registry YAML |
| `scope_trust_root_hash` | Combined SHA-256 of policy hash + registry hash |
| Optional `ledger_excerpt`, `quality_warnings`, signature fields |

Contract fixture: `tests/fixtures/contracts/pcs_manifest_contract.json`.

Key registry workflow: [key_management.md](key_management.md). See [pcs_export.md](pcs_export.md).

### Live validation (optional)

When `PCS_CORE_REPO_PATH` points to a PCS checkout:

```bash
export PCS_CORE_REPO_PATH=/path/to/pcs-core
scope export pcs --packet p.json --decision d.json --grant g.json --out ./pcs --validate --live
```

Candidate script paths:

- `scripts/validate_scope_artifact.py`
- `tools/validate_scope_artifact.py`
- `tests/fixtures/validate_scope_artifact.py`

Skips explicitly when repo path absent.

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

## Review queue (v0.7)

File-backed queue entries under `.scope/queues/` (override with `--queue-dir`).

Schema: `schemas/scope_review_queue.schema.json`.

Ten-state workflow: `open`, `assigned`, `in_review`, `needs_information`, `escalated`, `decided`, `granted`, `expired`, `closed`, `cancelled`. Grants require `decided → granted`; direct grant from open or in-review states is forbidden.

CLI: `scope review queue create|assign|status|list|decide|grant|close` plus transition commands (`in-review`, `needs-information`, etc.).

REST: full queue lifecycle under `/v0/review-queue/{id}/...`.

Quality metrics: `open_queue_count`, `overdue_queue_count` (open statuses include `in_review`, `needs_information`, `escalated`).

## Version alignment (v0.9)

| Artifact | Version field | Expected value |
|----------|---------------|----------------|
| SCOPE package | `pyproject.toml` / `scope/_version.py` | `0.9.0` |
| SCOPE packet | `packet_version` | `0.9.0` |
| SCOPE grant | `grant_version` | `0.9.0` |
| Quality report | `report_version` | `0.8` |
| Review queue | `queue_version` | `0.9.0` |
| AKTA review summary | `adapter_contract_version` | `scope-akta-review-v0.9` |
| PF obligation | `obligation_version` | `pf-core-v0.5` |
| PCS manifest | `manifest_version` | `pcs-v0.5` |
| Policy bundle | `version` in YAML | `scope-core-v0.9` |

## Environment paths and live demo

Partner repositories are referenced via environment variables (never committed):

| Variable | Required for | Example |
|----------|--------------|---------|
| `AKTA_REPO_PATH` | AKTA-side tooling / optional CI | `/opt/akta` |
| `PF_CORE_REPO_PATH` | PF live validation + violation loop | `/opt/pf-core` |
| `PCS_CORE_REPO_PATH` | PCS live validation | `/opt/pcs-core` |
| `SCOPE_REST_URL` | REST demo (`scripts/akta_rest_review.py`) | `http://127.0.0.1:8765` |
| `SCOPE_API_KEY` | Authenticated REST | (institutional secret) |
| `VSA_API_URL` | Scheduled VSA re-fetch | `https://vsa.example/api` |
| `VSA_API_TOKEN` | VSA bearer auth | (institutional secret) |

One-command ecosystem demo: [ecosystem_demo.md](ecosystem_demo.md).

PF violation feedback uses `scripts/pf_inject_violation.py` (loads `adapters/pf_core/export_obligation.py` output, records `runtime_scope_violation` via CLI or `POST /v0/ledger/violations`).

## External repo dependencies

These integrations require live services or repositories not present in this repo:

- **AKTA**: authoritative admissibility decisions and nested record storage
- **PF-Core**: runtime obligation enforcement at tool invocation (`pf-core-v0.5`)
- **PCS**: release pipeline ingestion and institutional signing workflows (`pcs-v0.5`)
- **VSA**: live ScientificReport generation from validation pipelines

Local adapters validate shapes and hashes by default. Cross-repo end-to-end tests run when env paths are configured (`tests/test_live_contracts.py`, optional CI job `live-ecosystem`).
