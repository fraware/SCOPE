# AKTA Integration

SCOPE begins when AKTA returns `review_required` or `authorization_required`.

## Inputs

- **AKTA Record** — scientific action context, artifacts, constraints
- **Review trigger** — requested tool, action type, admissibility

## Adapter

```python
from adapters.akta.import_trigger import load_review_trigger
from scope import ScopeEngine

trigger = load_review_trigger("review_trigger.json")
engine = ScopeEngine.from_policy_dir("policy/")
packet = engine.create_packet("akta_record.json", trigger)
```

## Required trigger fields

- `scientific_action_type` (e.g. `A5_protocol_modification`)
- `akta_admissibility` (`review_required` or `authorization_required`)
- `requested_tool`

SCOPE resolves required reviewer roles from `policy/role_to_action_matrix.yaml`.
