# SCOPE

Home: [https://github.com/fraware/SCOPE](https://github.com/fraware/SCOPE)

SCOPE is the Scoped Scientific Authorization Protocol.

AKTA can decide that an AI-shaped scientific action requires review or authorization. SCOPE turns that decision into a structured review packet, assigns the right reviewer role, captures a scoped decision, emits a bounded grant, enforces expiration, and produces artifacts that can be verified and packaged.

Review is not a checkbox. Review is a role, artifact, scope, expiration, and accountability trail.

## Quick start

```bash
pip install -e ".[dev]"
pytest
python evals/run_review_cases.py
```

## CLI

```bash
scope packet create --akta-record examples/protocol_change_review/akta_record.json \
  --akta-trigger examples/protocol_change_review/review_trigger.json \
  --out /tmp/packet.json

scope decision submit --packet /tmp/packet.json \
  --reviewer examples/protocol_change_review/reviewer_protocol_owner.json \
  --decision examples/protocol_change_review/decision.json \
  --out /tmp/decision.json

scope grant issue --packet /tmp/packet.json --decision /tmp/decision.json --out /tmp/grant.json

scope grant check --grant /tmp/grant.json --requested-tool robot_queue.submit \
  --context examples/protocol_change_review/current_context.json
```

## Python API

```python
from scope import ScopeEngine

engine = ScopeEngine.from_policy_dir("policy/")
packet = engine.create_packet("examples/protocol_change_review/akta_record.json",
                                "examples/protocol_change_review/review_trigger.json")
decision = engine.submit_decision(packet, {"reviewer_id": "r1", "role": "protocol_owner"}, {
    "type": "approve_narrower_scope",
    "approved_scope": "protocol_draft",
    "rationale": "Evidence supports validation draft only.",
})
grant = engine.issue_grant(packet, decision)
allowed = engine.check_grant(grant, "protocol_editor.draft_change", {"protocol_version": "protocol_v3"})
```

## Repository layout

- `scope/` - core protocol engine
- `schemas/` - JSON schemas for artifacts
- `policy/` - YAML policy files
- `adapters/` - AKTA, PF-Core, PCS, REST integrations
- `examples/` - scenario fixtures
- `evals/` - eight evaluation scenarios
- `tests/` - pytest suite
- `docs/` - protocol documentation

## License

MIT - see [LICENSE](LICENSE).
