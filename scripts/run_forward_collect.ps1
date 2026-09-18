# scripts/run_forward_collect.ps1 - daily forward-collector run (Phase 8 machinery).
#
# FAIL-SAFE BY DESIGN: 'collect' mode requires the human-authorization marker
# COLLECT_START_AUTHORIZED in project_audit/forward_monitoring/. Without it the
# collector logs "collect BLOCKED" and exits 5 - a harmless daily bookkeeping
# line. Collection starts automatically only after the human stamps the marker
# AND forward_start_timestamp (see FORWARD_START_AUTHORIZATION.md).

$root = Split-Path -Parent $PSScriptRoot
Set-Location -Path $root
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path (Join-Path $root "project_audit\forward_monitoring\forward_collect.log") `
    -Value "=== scheduled run $stamp ==="
python "project_audit\forward_monitoring\forward_collector.py" collect *>> `
    (Join-Path $root "project_audit\forward_monitoring\forward_collect.log")
