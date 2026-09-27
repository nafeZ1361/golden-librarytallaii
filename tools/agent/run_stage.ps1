param(
    [Parameter(Mandatory=$true)]
    [string]$Stage
)

$ErrorActionPreference = "Stop"
Set-Location (git rev-parse --show-toplevel)

function Run-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "=== $Name ==="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Write-Host "STAGE=$Stage"
Run-Step "Git status" { git status --short }
Run-Step "Branch" { git branch --show-current }
Run-Step "HEAD" { git rev-parse HEAD }

if (Test-Path ".venv\Scripts\python.exe") {
    $Python = (Resolve-Path ".venv\Scripts\python.exe").Path
} else {
    $Python = "python"
}

Write-Host "PYTHON=$Python"
& $Python --version
if ($LASTEXITCODE -ne 0) { throw "Python unavailable" }

if (Test-Path "requirements.txt") {
    Write-Host "=== Required ML dependencies ==="
    Get-Content requirements.txt | Select-String "^(numpy|pandas|scikit-learn|pandas-ta)=="
}

Write-Host "=== Stage executor handoff ==="
Write-Host "The AI agent must now perform the stage-specific audit, tests and validation."
Write-Host "This runner intentionally does not auto-edit, reset, clean, commit, or advance stages."
