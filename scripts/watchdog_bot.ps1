# scripts/watchdog_bot.ps1 - production-safe bot supervisor (Phase 7).
#
# Contract:
#   - DEMO ONLY: launches bot_runner.py with DRY_RUN=0/ALLOW_LIVE=1; bot_runner
#     hard-refuses any non-demo account (trade_mode guard) and refuses to run
#     without ALLOW_LIVE=1. Real-money trading stays structurally denied (CP18).
#   - SINGLE INSTANCE: PID-file guard - if a live bot_runner python process is
#     already recorded, this run is a no-op (safe for frequent task triggers).
#   - AUTO-RESTART: designed for a Scheduled Task trigger every 5 minutes +
#     at logon; if the bot died, this restarts it and logs the failure.
#   - LOGGING: bot stdout/stderr -> logs\bot_runner_YYYYMMDD.{log,err.log};
#     watchdog events -> logs\watchdog.log. Failure history is never deleted.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -Path $root
$logDir = Join-Path $root "logs"
$pidFile = Join-Path $logDir "bot_runner.pid"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-WatchdogLog([string]$msg) {
    Add-Content -Path (Join-Path $logDir "watchdog.log") -Value "[$stamp] $msg"
}

# 1) liveness: PID file + process table (python name check guards PID reuse)
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($oldPid) {
        $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match "python") {
            exit 0   # alive -> no-op
        }
        Write-WatchdogLog "stale/dead PID $oldPid found -> restarting bot (crash recovery)"
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# 2) launch fresh instance (credentials from User registry, never in files)
$env:DRY_RUN = "0"
$env:ALLOW_LIVE = "1"
$env:TELEGRAM_BOT_TOKEN = [Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN','User')
$env:TELEGRAM_CHANNEL_ID = [Environment]::GetEnvironmentVariable('TELEGRAM_CHANNEL_ID','User')
$env:TELEGRAM_PROXY = [Environment]::GetEnvironmentVariable('TELEGRAM_PROXY','User')

$day = Get-Date -Format "yyyyMMdd"
$outLog = Join-Path $logDir "bot_runner_$day.log"
$errLog = Join-Path $logDir "bot_runner_$day.err.log"
$p = Start-Process -FilePath "C:\Python312\python.exe" `
        -ArgumentList "bot_runner.py" `
        -WorkingDirectory $root `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
        -WindowStyle Hidden -PassThru
if ($p) {
    Set-Content -Path $pidFile -Value $p.Id
    Write-WatchdogLog "started bot_runner PID=$($p.Id) (demo-only guard active)"
    exit 0
} else {
    Write-WatchdogLog "FAILED to start bot_runner"
    exit 1
}
