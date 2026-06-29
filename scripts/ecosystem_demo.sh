#!/usr/bin/env bash
# Ecosystem demo v2: AKTA → SCOPE → PF → PCS → ledger violation → quality report.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
SCOPE_CMD=(python -m scope.cli)

AKTA_TRIGGER="${AKTA_TRIGGER:-examples/protocol_drift/review_trigger.json}"
AKTA_RECORD="${AKTA_RECORD:-examples/protocol_drift/akta_record.json}"
REVIEWER="${REVIEWER:-examples/protocol_drift/reviewer_protocol_owner.json}"
GRANT_SCOPE="${GRANT_SCOPE:-protocol_draft}"
OUT_DIR="${OUT_DIR:-/tmp/scope_ecosystem_demo}"
POLICY="${POLICY:-policy/}"
QUEUE_DIR="${QUEUE_DIR:-.scope/queues}"
LEDGER="${LEDGER:-.scope/ecosystem_ledger.jsonl}"
USE_REST="${USE_REST:-false}"
SCOPE_REST_URL="${SCOPE_REST_URL:-http://127.0.0.1:8765}"

mkdir -p "$OUT_DIR" "$QUEUE_DIR"
rm -f "$LEDGER"

SIGN_ARGS=()
if [[ -n "${SIGNING_KEY:-}" ]]; then
  SIGN_ARGS=(--signing-key "$SIGNING_KEY")
fi

echo "== Step 1: AKTA → SCOPE review =="
if [[ "$USE_REST" == "true" ]]; then
  python scripts/akta_rest_review.py \
    --akta-trigger "$AKTA_TRIGGER" \
    --akta-record "$AKTA_RECORD" \
    --reviewer "$REVIEWER" \
    --grant-scope "$GRANT_SCOPE" \
    --decision-rationale "Ecosystem demo live approval" \
    --out-dir "$OUT_DIR" \
    --queue-dir "$QUEUE_DIR" \
    --rest-url "$SCOPE_REST_URL" \
    "${SIGN_ARGS[@]/#/--signing-key }"
else
  "${SCOPE_CMD[@]}" akta review \
    --akta-trigger "$AKTA_TRIGGER" \
    --akta-record "$AKTA_RECORD" \
    --grant-scope "$GRANT_SCOPE" \
    --reviewer "$REVIEWER" \
    --decision-rationale "Ecosystem demo live approval" \
    --out-dir "$OUT_DIR" \
    --queue-dir "$QUEUE_DIR" \
    --ledger "$LEDGER" \
    --policy "$POLICY" \
    "${SIGN_ARGS[@]}"
fi

PACKET="$OUT_DIR/scope_review_packet.json"
DECISION="$OUT_DIR/scope_decision.json"
GRANT="$OUT_DIR/scope_grant.json"
PF_OUT="$OUT_DIR/pf_obligation.json"
PCS_OUT="$OUT_DIR/pcs_export"
QUALITY_OUT="$OUT_DIR/quality_report.json"

echo "== Step 2: SCOPE → PF obligation export =="
"${SCOPE_CMD[@]}" export pf --grant "$GRANT" --out "$PF_OUT" --validate --live

echo "== Step 3: PF simulated block → SCOPE violation =="
python scripts/pf_inject_violation.py \
  --grant "$GRANT" \
  --ledger "$LEDGER" \
  --policy "$POLICY" \
  ${SCOPE_REST_URL:+--rest-url "$SCOPE_REST_URL"}

echo "== Step 4: SCOPE → PCS archive export =="
"${SCOPE_CMD[@]}" export pcs \
  --packet "$PACKET" \
  --decision "$DECISION" \
  --grant "$GRANT" \
  --out "$PCS_OUT" \
  --validate \
  --live \
  --policy "$POLICY"

echo "== Step 5: Quality report (expect non-zero violation rate) =="
"${SCOPE_CMD[@]}" quality report --ledger "$LEDGER" --out "$QUALITY_OUT" --queue-dir "$QUEUE_DIR"

python - "$QUALITY_OUT" <<'PY'
import json, sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rate = report.get("metrics", {}).get("post_approval_runtime_violation_rate", 0)
count = report.get("metrics", {}).get("runtime_violation_outcome_count", 0)
print(f"post_approval_runtime_violation_rate={rate}")
print(f"runtime_violation_outcome_count={count}")
if rate <= 0 or count <= 0:
    sys.exit("Expected non-zero runtime violation metrics after PF inject")
PY

echo "Ecosystem demo complete -> $OUT_DIR"
