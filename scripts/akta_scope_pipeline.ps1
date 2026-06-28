# AKTA → SCOPE demo pipeline (PowerShell)
# Reads AKTA trigger/record paths, runs scope akta review, writes queue + PCS export.

param(
    [Parameter(Mandatory = $true)][string]$AktaTrigger,
    [Parameter(Mandatory = $true)][string]$AktaRecord,
    [Parameter(Mandatory = $true)][string]$GrantScope,
    [Parameter(Mandatory = $true)][string]$Reviewer,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string]$Policy = "policy/",
    [string]$QueueDir = ".scope/queues",
    [string]$Ledger = ".scope/ledger.jsonl",
    [string]$SigningKey = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path $QueueDir | Out-Null

$aktaArgs = @(
    "akta", "review",
    "--akta-trigger", $AktaTrigger,
    "--akta-record", $AktaRecord,
    "--grant-scope", $GrantScope,
    "--reviewer", $Reviewer,
    "--decision-rationale", "AKTA pipeline demo approval",
    "--out-dir", $OutDir,
    "--queue-dir", $QueueDir,
    "--ledger", $Ledger,
    "--policy", $Policy
)
if ($SigningKey) {
    $aktaArgs += @("--signing-key", $SigningKey)
}
scope @aktaArgs

$packet = Join-Path $OutDir "scope_review_packet.json"
$decision = Join-Path $OutDir "scope_decision.json"
$grant = Join-Path $OutDir "scope_grant.json"
$pcsOut = Join-Path $OutDir "pcs_export"

scope export pcs --packet $packet --decision $decision --grant $grant --out $pcsOut --validate --policy $Policy
Write-Host "Pipeline complete -> $OutDir (PCS: $pcsOut)"
