# scripts/_register_tasks.ps1 - one-shot registration of the two scheduled tasks.
# Derives the repo root from $PSScriptRoot (scripts/ parent) - ASCII-only file.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# 1) bot watchdog: at logon + every 5 minutes (single-instance guard inside)
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\scripts\watchdog_bot.ps1`""
$t1 = New-ScheduledTaskTrigger -AtLogOn
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "GoldenLibrary-BotWatchdog" -Action $action `
    -Trigger $t1, $t2 -Settings $settings `
    -Description "Golden Library demo bot supervisor: single instance, restart<=5min, DEMO-only (in-code trade_mode guard)" `
    -Force | Out-Null

# 2) forward collector: daily 09:05 (fail-closed until human marker)
$action2 = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\scripts\run_forward_collect.ps1`""
$t3 = New-ScheduledTaskTrigger -Daily -At "09:05"
$settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "GoldenLibrary-ForwardCollector" -Action $action2 `
    -Trigger $t3 -Settings $settings2 `
    -Description "Daily FD-CP5.9 forward collector run - BLOCKED until human stamps COLLECT_START_AUTHORIZED" `
    -Force | Out-Null

Get-ScheduledTask -TaskName "GoldenLibrary-*" | Select-Object TaskName, State | Format-Table -AutoSize
