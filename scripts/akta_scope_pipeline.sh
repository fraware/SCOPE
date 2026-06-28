#!/usr/bin/env bash
# AKTA → SCOPE demo pipeline: packet, decision, grant, queue, PCS export.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AKTA_TRIGGER="${1:?akta trigger path required}"
AKTA_RECORD="${2:?akta record path required}"
GRANT_SCOPE="${3:?grant scope required}"
REVIEWER="${4:?reviewer json path required}"
OUT_DIR="${5:?output dir required}"
POLICY="${POLICY:-policy/}"
QUEUE_DIR="${QUEUE_DIR:-.scope/queues}"
LEDGER="${LEDGER:-.scope/ledger.jsonl}"

mkdir -p "$OUT_DIR" "$QUEUE_DIR"

SIGN_ARGS=()
if [[ -n "${SIGNING_KEY:-}" ]]; then
  SIGN_ARGS=(--signing-key "$SIGNING_KEY")
fi

scope akta review \
  --akta-trigger "$AKTA_TRIGGER" \
  --akta-record "$AKTA_RECORD" \
  --grant-scope "$GRANT_SCOPE" \
  --reviewer "$REVIEWER" \
  --decision-rationale "AKTA pipeline demo approval" \
  --out-dir "$OUT_DIR" \
  --queue-dir "$QUEUE_DIR" \
  --ledger "$LEDGER" \
  --policy "$POLICY" \
  "${SIGN_ARGS[@]}"

scope export pcs \
  --packet "$OUT_DIR/scope_review_packet.json" \
  --decision "$OUT_DIR/scope_decision.json" \
  --grant "$OUT_DIR/scope_grant.json" \
  --out "$OUT_DIR/pcs_export" \
  --validate \
  --policy "$POLICY"

echo "Pipeline complete -> $OUT_DIR"
