# AKTA ↔ SCOPE evidence vocabulary mapping

AKTA and SCOPE share an evidence-state vocabulary with historical aliases. SCOPE treats the states below as **weak evidence** for quality warnings (`approval_despite_low_evidence`).

## Weak evidence states (SCOPE)

| SCOPE state | AKTA alias(es) | Notes |
|-------------|----------------|-------|
| *(empty)* | *(missing)* | Treated as unknown / no signal |
| `E0_unknown` | `E0_unknown` | Default when evidence not supplied |
| `E0_no_evidence` | `E0_no_evidence`, `no_evidence` | Explicit absence of evidence |
| `E1_hypothesis` | `E1_hypothesis` | Pre-data hypothesis |
| `E1_weak_signal` | `E1_weak_signal` | Weak qualitative signal |
| `E1_anecdotal_or_informal_observation` | `E1_anecdotal`, `anecdotal_or_informal_observation` | Informal observation only |
| `E2_preliminary` | `E2_preliminary` | Early preliminary work |
| `E2_preliminary_signal` | `E2_preliminary_signal` | Preliminary quantitative signal |

## Strong evidence states (no low-evidence warning)

| SCOPE state | AKTA alias(es) | Notes |
|-------------|----------------|-------|
| `E3_replicated_or_externally_validated` | `E3_replicated` | External replication |
| `E4_internally_consistent_evidence` | `E4_internally_consistent_evidence` | Internally consistent body of evidence |
| `E5_high_confidence_evidence` | `E5_high_confidence` | High-confidence evidentiary basis |

## Import behavior

- AKTA record/trigger `scientific_context.evidence_state` is normalized to canonical SCOPE states at the packet adapter boundary.
- Non-canonical AKTA aliases (e.g. `no_evidence`, `E1_anecdotal`, `E3_replicated`) are mapped per the tables above.
- When normalization changes the value, the original AKTA alias is preserved in `scientific_context.metadata.akta_evidence_state`.
- Flat AKTA `evidence_state` on records is merged into `scientific_context` when nested context is absent or default.
- Quality warnings use SCOPE `WEAK_EVIDENCE_STATES` in `scope/quality.py` against the canonical packet state.

## Quality warning

When a reviewer submits an approval decision (`approve`, `approve_narrower_scope`) and the packet `scientific_context.evidence_state` is in the weak set, SCOPE emits ledger event `quality_warning_emitted` with `warning_type: approval_despite_low_evidence`.

See [external_integration_contracts.md](external_integration_contracts.md) for AKTA import behavior and [quality_metrics.md](quality_metrics.md) for related metrics.
