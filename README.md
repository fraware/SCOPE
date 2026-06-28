# SCOPE

Home: [https://github.com/fraware/SCOPE](https://github.com/fraware/SCOPE)

SCOPE is the Scoped Scientific Authorization Protocol (v0.4).

AKTA can decide that an AI-shaped scientific action requires review or authorization. SCOPE turns that decision into a structured review packet, assigns the right reviewer role, captures a scoped decision, emits a bounded grant, enforces expiration, and produces artifacts that can be verified and packaged.

Review is not a checkbox. Review is a role, artifact, scope, expiration, and accountability trail.

## Quick start

```bash
pip install -e ".[dev]"
pytest
python evals/run_review_cases.py
```

## CLI

### Packet workflow

```bash
scope packet create --akta-record examples/protocol_change_review/akta_record.json \
  --akta-trigger examples/protocol_change_review/review_trigger.json \
  --vsa-report adapters/vsa/examples/scientific_report_example.json \
  --out /tmp/packet.json

scope packet validate /tmp/packet.json

scope packet render /tmp/packet.json --format markdown --out /tmp/packet.md
```

### Decision and grant

```bash
scope decision submit --packet /tmp/packet.json \
  --reviewer examples/protocol_change_review/reviewer_protocol_owner.json \
  --decision examples/protocol_change_review/decision.json \
  --out /tmp/decision.json

scope grant issue --packet /tmp/packet.json --decision /tmp/decision.json --out /tmp/grant.json

scope grant check --grant /tmp/grant.json --requested-tool robot_queue.submit \
  --context examples/protocol_change_review/current_context.json \
  --ledger /tmp/scope_events.jsonl

scope grant revoke --grant-id SCOPE-GRANT-XXXXXX --ledger /tmp/scope_events.jsonl

scope grant status --grant-id SCOPE-GRANT-XXXXXX --ledger /tmp/scope_events.jsonl
```

### Multi-reviewer sessions (A6 and similar)

```bash
scope review session create --packet /tmp/packet.json --out /tmp/session.json \
  --session-store json --session-dir /tmp/sessions

scope review session vote --session /tmp/session.json --packet /tmp/packet.json \
  --reviewer examples/reviewer_domain_scientist.json \
  --decision examples/decision_ds.json --out /tmp/decision_ds.json \
  --session-store json --session-dir /tmp/sessions

scope review session vote --session /tmp/session.json --packet /tmp/packet.json \
  --reviewer examples/reviewer_protocol_owner.json \
  --decision examples/decision_po.json --out /tmp/decision_po.json \
  --session-store json --session-dir /tmp/sessions

scope review session issue-grant --session /tmp/session.json --packet /tmp/packet.json \
  --decision /tmp/decision_ds.json --decision /tmp/decision_po.json --out /tmp/grant.json \
  --session-store json --session-dir /tmp/sessions

scope review session status --session-id SCOPE-SESS-XXXXXX --packet /tmp/packet.json \
  --session-store json --session-dir /tmp/sessions
```

Session backends: `memory` (default), `json`, `sqlite`. Use `--session-dir` for persistence path.

Review lifecycle ledger events:

```bash
scope review open --packet-id SCOPE-PKT-XXXXXX --actor-id reviewer-1 --ledger /tmp/scope_events.jsonl

scope review view-artifact --packet-id SCOPE-PKT-XXXXXX --artifact protocol_diff_ref \
  --actor-id reviewer-1 --ledger /tmp/scope_events.jsonl
```

Quorum modes (`require_all`, `require_any`, `n_of_m`, `statistical_co_review`) and
`safety_veto_roles` are configured via optional `--quorum-policy` on session create.

### Signing and production mode

Production mode requires a signed decision before grant issue. Decisions may be submitted unsigned, then signed:

```bash
export SCOPE_PRODUCTION_MODE=true

scope decision submit --packet /tmp/packet.json --reviewer reviewer.json \
  --decision decision.json --out /tmp/decision.json

scope decision sign --decision /tmp/decision.json --key keys/reviewer.pem --out /tmp/signed_decision.json
scope decision validate --require-signature /tmp/signed_decision.json

scope grant issue --packet /tmp/packet.json --decision /tmp/signed_decision.json --out /tmp/grant.json
scope grant sign --grant /tmp/grant.json --key keys/reviewer.pem --out /tmp/signed_grant.json
scope verify --artifact /tmp/signed_decision.json --public-key keys/reviewer.pub --type decision
```

Use `--public-key` for verification without private key access. `--key` remains for dev signing only.

See [docs/trusted_boundary.md](docs/trusted_boundary.md) for trust assumptions.

### Export and quality

```bash
scope export pf --grant /tmp/grant.json --out /tmp/pf_obligation.json --validate

scope export pcs --packet /tmp/packet.json --decision /tmp/decision.json \
  --grant /tmp/grant.json --out /tmp/pcs_bundle --validate

scope quality report --ledger /tmp/scope_events.jsonl --out /tmp/quality_report.json
```

## REST API

Optional FastAPI server (install with `pip install -e ".[rest]"`):

```bash
uvicorn adapters.generic_rest.server:app --reload
```

Set `SCOPE_LEDGER_PATH` for ledger-backed grant check/revoke/status.
Set `SCOPE_SIGNING_KEY` for sign/verify endpoints.
Set `SCOPE_SESSION_STORE` and `SCOPE_SESSION_DIR` for persistent review sessions (`json` or `sqlite`).
Set `SCOPE_API_KEY` to require `Authorization: Bearer <key>` on all endpoints except `/v0/health`.
Set `SCOPE_REVIEW_ROUTE_PROMOTION=true` (default) to promote valid AKTA `review_scope` values to `requested_scope`.

Grant check returns `{allowed, reason, code}` where `code` is `allowed`, `tool_blocked`, `tool_not_allowed`, `grant_expired`, or `grant_revoked`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v0/health` | Health check |
| POST | `/v0/packets` | Create packet |
| POST | `/v0/packets/validate` | Validate packet |
| POST | `/v0/packets/render` | Render packet (markdown/html) |
| POST | `/v0/decisions` | Submit decision |
| POST | `/v0/decisions/sign` | Sign decision |
| POST | `/v0/review-sessions` | Create review session |
| GET | `/v0/review-sessions/{id}` | Session status |
| POST | `/v0/review-sessions/{id}/votes` | Submit session vote |
| POST | `/v0/review-sessions/{id}/grants` | Issue grant from session |
| POST | `/v0/grants` | Issue grant |
| POST | `/v0/grants/check` | Runtime grant check |
| POST | `/v0/grants/revoke` | Revoke grant |
| GET | `/v0/grants/{id}/status` | Grant ledger status |
| POST | `/v0/grants/sign` | Sign grant |
| POST | `/v0/verify` | Verify signed artifact |
| GET | `/v0/quality` | Quality report |
| POST | `/v0/export/pf` | PF-Core obligation export |
| POST | `/v0/export/pf/validate` | Validate PF export |
| POST | `/v0/export/pcs` | PCS bundle export |
| POST | `/v0/export/pcs/validate` | Validate PCS export |

Full cross-repo demo: [docs/akta_scope_demo.md](docs/akta_scope_demo.md).
Integration contracts: [docs/external_integration_contracts.md](docs/external_integration_contracts.md).

## Python API

```python
from scope import ScopeEngine

engine = ScopeEngine.from_policy_dir("policy/", ledger_path="logs/scope_events.jsonl")
packet = engine.create_packet("examples/protocol_change_review/akta_record.json",
                                "examples/protocol_change_review/review_trigger.json")
decision = engine.submit_decision(packet, {"reviewer_id": "r1", "role": "protocol_owner"}, {
    "type": "approve_narrower_scope",
    "approved_scope": "protocol_draft",
    "rationale": "Evidence supports validation draft only.",
})
grant = engine.issue_grant(packet, decision)
allowed = engine.check_grant_detailed(grant, "protocol_editor.draft_change", {"protocol_version": "protocol_v3"})
```

## Repository layout

- `scope/` - core protocol engine
- `schemas/` - JSON schemas for artifacts
- `policy/` - YAML policy files (`scope-core-v0.4`) and domain overlays
- `adapters/` - AKTA, VSA, PF-Core, PCS, REST integrations
- `examples/` - scenario fixtures
- `evals/` - eight core evaluation scenarios (+ four extended with `--extended`)
- `tests/` - pytest suite
- `docs/` - protocol documentation

## License

MIT - see [LICENSE](LICENSE).
