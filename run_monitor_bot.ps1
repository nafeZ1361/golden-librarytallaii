# run_monitor_bot.ps1 — launcher for the READ-ONLY Telegram monitor bot.
# Reads credentials from the USER environment (registry) — no secrets in files.
$env:TELEGRAM_BOT_TOKEN = [Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN','User')
$env:TELEGRAM_ALLOWED_CHATS = [Environment]::GetEnvironmentVariable('TELEGRAM_ALLOWED_CHATS','User')
$env:TELEGRAM_CHANNEL_ID = [Environment]::GetEnvironmentVariable('TELEGRAM_CHANNEL_ID','User')
$env:TELEGRAM_PROXY = [Environment]::GetEnvironmentVariable('TELEGRAM_PROXY','User')
Set-Location -Path $PSScriptRoot
python -m module.monitor_bot
