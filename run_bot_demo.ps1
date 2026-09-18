# run_bot_demo.ps1 - launch bot_runner in DEMO-LIVE mode (orders ON, DEMO account ONLY).
#
# Preconditions:
#   1. MT5 terminal is running and logged into a DEMO account (the runner
#      hard-refuses to start on a non-demo account - trade_mode guard).
#   2. Telegram credentials are set in the User environment
#      (TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL_ID [+ TELEGRAM_PROXY]).
#      Every opened order is then reported in Persian: direction, entry, SL, TP.
#
# To stop: Ctrl+C in this window. Kill-switches (daily 5% / total 12%) remain active.

$env:DRY_RUN = "0"
$env:ALLOW_LIVE = "1"
$env:TELEGRAM_BOT_TOKEN = [Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN','User')
$env:TELEGRAM_CHANNEL_ID = [Environment]::GetEnvironmentVariable('TELEGRAM_CHANNEL_ID','User')
$env:TELEGRAM_PROXY = [Environment]::GetEnvironmentVariable('TELEGRAM_PROXY','User')
Set-Location -Path $PSScriptRoot
Write-Host "=== DEMO-LIVE launcher: orders allowed on DEMO accounts only ===" -ForegroundColor Yellow
python bot_runner.py
