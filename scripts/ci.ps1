$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

function Invoke-Pip {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$PipArgs
    )

    $savedNativePref = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
        $savedNativePref = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    $savedErrorPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & python -m pip @PipArgs 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                Write-Host $_.ToString()
            } else {
                Write-Host $_
            }
        }
        if ($LASTEXITCODE -ne 0) {
            throw "python -m pip failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        $ErrorActionPreference = $savedErrorPref
        if ($null -ne $savedNativePref) {
            $PSNativeCommandUseErrorActionPreference = $savedNativePref
        }
    }
}

Invoke-Pip install --upgrade pip setuptools wheel
Invoke-Pip install --editable ".[dev]"
ruff check scope tests evals adapters
mypy scope
pytest
python evals/run_review_cases.py --extended