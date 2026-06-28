# Publication claim review (missing co-review)

Scenario: publication claim escalation (A10) requires `publication_reviewer` plus `domain_scientist` co-review. Approval by publication reviewer alone must fail.

Single-decision submit cannot satisfy `require_all` multi-role actions; use a review session for the success path.

## Run (expect failure)

```bash
scope packet create \
  --akta-record examples/publication_claim_review/akta_record.json \
  --akta-trigger examples/publication_claim_review/review_trigger.json \
  --out /tmp/pub_packet.json

scope decision submit \
  --packet /tmp/pub_packet.json \
  --reviewer examples/publication_claim_review/reviewer_publication.json \
  --decision examples/publication_claim_review/decision.json \
  --out /tmp/pub_decision.json
```

Expected: co-review validation error.

See `evals/scenarios/publication_claim_requires_domain_review.json`.

For multi-reviewer session workflow, see [reviewer_guide.md](../../docs/reviewer_guide.md).
