# AKTA Integration

SCOPE begins when AKTA returns `review_required` or `authorization_required`.

## Primary integration path

For packet → decision → grant in one step, use:

```bash
scope akta review \
  --akta-record path/to/akta_record.json \
  --akta-trigger path/to/review_trigger.json \
  --grant-scope protocol_draft \
  --reviewer path/to/reviewer.json \
  --decision-rationale "Rationale text." \
  --out-dir /tmp/akta_review_out
```

REST equivalent: `POST /v0/akta/review`.

Output contract: [akta_review_contract.md](akta_review_contract.md). Full demo: [akta_scope_demo.md](akta_scope_demo.md). Field mappings: [external_integration_contracts.md](external_integration_contracts.md).

## Inputs

- **AKTA Record** — scientific action context, artifacts, constraints
- **Review trigger** — requested tool, action type, admissibility

Golden fixtures: `adapters/akta/examples/` (see [adapters/akta/examples/README.md](../adapters/akta/examples/README.md)).

## Low-level adapter (Python)

```python
from adapters.akta.import_trigger import load_review_trigger
from scope import ScopeEngine

trigger = load_review_trigger("review_trigger.json")
engine = ScopeEngine.from_policy_dir("policy/")
packet = engine.create_packet("akta_record.json", trigger)
```

Use this path when you need custom packet enrichment (VSA reports, manual review steps) before decision submit.

## Required trigger fields

- `scientific_action_type` (e.g. `A5_protocol_modification`)
- `akta_admissibility` (`review_required` or `authorization_required`)
- `requested_tool`

SCOPE resolves required reviewer roles from `policy/role_to_action_matrix.yaml`.

## v0.7 provenance on review output

Decisions and grants from `scope akta review` record:

- Identity assurance level (IAL0–IAL4) — see [identity_assurance.md](identity_assurance.md)
- Signing assurance level (SAL0–SAL4) — see [signing_assurance.md](signing_assurance.md)
- Two-stage `authority_checks` when RBAC is enforced — see [rbac_scope_authority.md](rbac_scope_authority.md)
