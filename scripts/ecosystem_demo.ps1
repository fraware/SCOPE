# Ecosystem demo v2: AKTA → SCOPE → PF → PCS → ledger violation → quality report.
param(
    [string]$AktaTrigger = "examples/protocol_drift/review_trigger.json",
    [string]$AktaRecord = "examples/protocol_drift/akta_record.json",
    [string]$Reviewer = "examples/protocol_drift/reviewer_protocol_owner.json",
    [string]$GrantScope = "protocol_draft",
    [string]$OutDir = "$env:TEMP\scope_ecosystem_demo",
    [string]$Policy = "policy/",
    [string]$QueueDir = ".scope/queues",
    [string]$Ledger = ".scope/ecosystem_ledger.jsonl",
    [switch]$UseRest,
    [string]$ScopeRestUrl = "http://127.0.0.1:8765",
    [string]$SigningKey = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

New-Item -ItemType Directory -Force -Path $OutDir, $QueueDir | Out-Null
if (Test-Path $Ledger) { Remove-Item $Ledger -Force }

Write-Host "== Step 1: AKTA → SCOPE review =="
if ($UseRest) {
    $restArgs = @(
        "scripts/akta_rest_review.py",
        "--akta-trigger", $AktaTrigger,
        "--akta-record", $AktaRecord,
        "--reviewer", $Reviewer,
        "--grant-scope", $GrantScope,
        "--decision-rationale", "Ecosystem demo live approval",
        "--out-dir", $OutDir,
        "--queue-dir", $QueueDir,
        "--rest-url", $ScopeRestUrl
    )
    if ($SigningKey) { $restArgs += @("--signing-key", $SigningKey) }
    python @restArgs
} else {
    $aktaArgs = @(
        "akta", "review",
        "--akta-trigger", $AktaTrigger,
        "--akta-record", $AktaRecord,
        "--grant-scope", $GrantScope,
        "--reviewer", $Reviewer,
        "--decision-rationale", "Ecosystem demo live approval",
        "--out-dir", $OutDir,
        "--queue-dir", $QueueDir,
        "--ledger", $Ledger,
        "--policy", $Policy
    )
    if ($SigningKey) { $aktaArgs += @("--signing-key", $SigningKey) }
    scope @aktaArgs
}

$packet = Join-Path $OutDir "scope_review_packet.json"
$decision = Join-Path $OutDir "scope_decision.json"
$grant = Join-Path $OutDir "scope_grant.json"
$pfOut = Join-Path $OutDir "pf_obligation.json"
$pcsOut = Join-Path $OutDir "pcs_export"
$qualityOut = Join-Path $OutDir "quality_report.json"

Write-Host "== Step 2: SCOPE → PF obligation export =="
scope export pf --grant $grant --out $pfOut --validate --live

Write-Host "== Step 3: PF simulated block → SCOPE violation =="
$violationArgs = @("scripts/pf_inject_violation.py", "--grant", $grant, "--ledger", $Ledger, "--policy", $Policy)
if ($UseRest) { $violationArgs += @("--rest-url", $ScopeRestUrl) }
python @violationArgs

Write-Host "== Step 4: SCOPE → PCS archive export =="
scope export pcs --packet $packet --decision $decision --grant $grant --out $pcsOut --validate --live --policy $Policy

Write-Host "== Step 5: Quality report =="
scope quality report --ledger $Ledger --out $qualityOut --queue-dir $QueueDir

python -c @"
import json, sys
from pathlib import Path
report = json.loads(Path(r'$qualityOut').read_text(encoding='utf-8'))
rate = report.get('metrics', {}).get('post_approval_runtime_violation_rate', 0)
count = report.get('metrics', {}).get('runtime_violation_outcome_count', 0)
print(f'post_approval_runtime_violation_rate={rate}')
print(f'runtime_violation_outcome_count={count}')
if rate <= 0 or count <= 0:
    raise SystemExit('Expected non-zero runtime violation metrics after PF inject')
"@

Write-Host "Ecosystem demo complete -> $OutDir"
