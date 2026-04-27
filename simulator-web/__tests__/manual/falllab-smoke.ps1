# ---------------------------------------------------------------------------
# Module H — FallLab buttons end-to-end smoke (manual, requires BE running).
#
# What it does:
#   1. Pings /api/sim/health to confirm BE is up.
#   2. Picks the first device returned by /api/sim/devices.
#   3. Starts a session if none is running, then targets one device.
#   4. Fires every FallLab button (false_fall / fall_brief / confirmed /
#      fall_no_response / stress / neutral / sos_triggered / sos_cancel)
#      against the picked device, asserting each returns 204 (or the
#      documented success status) and printing the resulting fall_state
#      after each call.
#
# Usage (from a powershell shell, with BE on the default port):
#   ./simulator-web/__tests__/manual/falllab-smoke.ps1
#
# Override the API base via env if needed:
#   $env:VITE_API_BASE_URL = "http://localhost:8090"
#   ./simulator-web/__tests__/manual/falllab-smoke.ps1
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:VITE_API_BASE_URL) { $env:VITE_API_BASE_URL } else { "http://localhost:8090" }
Write-Host "[falllab-smoke] BaseUrl = $BaseUrl" -ForegroundColor Cyan

function Invoke-Sim {
    param(
        [Parameter(Mandatory)] [string] $Method,
        [Parameter(Mandatory)] [string] $Path,
        [object] $Body = $null
    )
    $url = "$BaseUrl$Path"
    try {
        if ($Body -ne $null) {
            $json = $Body | ConvertTo-Json -Compress
            return Invoke-RestMethod -Method $Method -Uri $url -ContentType "application/json" -Body $json -TimeoutSec 10
        }
        return Invoke-RestMethod -Method $Method -Uri $url -TimeoutSec 10
    } catch {
        Write-Host "[falllab-smoke] $Method $url failed: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

# 1) Health check
Write-Host "`n=== 1) /api/sim/health ===" -ForegroundColor Yellow
$health = Invoke-Sim -Method GET -Path "/api/sim/health"
Write-Host ("schemaVersion = {0}, runtime.state = {1}" -f $health.schemaVersion, $health.runtime.state)

# 2) Pick first device
Write-Host "`n=== 2) /api/sim/devices ===" -ForegroundColor Yellow
$devices = Invoke-Sim -Method GET -Path "/api/sim/devices"
if (-not $devices -or $devices.Count -eq 0) {
    throw "No simulator devices found.  Create one via the Devices page first."
}
$device = $devices[0]
Write-Host ("Picked device: {0} ({1})" -f $device.name, $device.id)

# 3) Find or create a running session targeting the picked device
Write-Host "`n=== 3) /api/sim/sessions ===" -ForegroundColor Yellow
$sessions = Invoke-Sim -Method GET -Path "/api/sim/sessions"
$session = $sessions | Where-Object { $_.status -eq "running" -and ($_.deviceIds -contains $device.id) } | Select-Object -First 1
if (-not $session) {
    Write-Host "No running session covers $($device.id); creating + starting…" -ForegroundColor DarkYellow
    $created = Invoke-Sim -Method POST -Path "/api/sim/sessions" -Body @{
        device_ids = @($device.id)
        scenario_id = $null
    }
    $session = Invoke-Sim -Method POST -Path "/api/sim/sessions/$($created.id)/start"
}
Write-Host ("Session: {0} (status = {1})" -f $session.id, $session.status)

# 4) Fire every FallLab action and observe fall-state transitions
$actions = @(
    @{ kind = "fall_event";  variant = "false_fall";       label = "Té ngã giả (false_fall)" },
    @{ kind = "fall_event";  variant = "fall_brief";       label = "Té ngã nhẹ (fall_brief)" },
    @{ kind = "fall_event";  variant = "confirmed";        label = "Té ngã xác nhận (confirmed)" },
    @{ kind = "fall_event";  variant = "fall_no_response"; label = "Không phản hồi (fall_no_response)" },
    @{ kind = "event";       eventType = "stress";         label = "⚡ Gây căng thẳng (stress)" },
    @{ kind = "event";       eventType = "neutral";        label = "Bình thường (neutral)" },
    @{ kind = "event";       eventType = "sos_triggered";  label = "SOS thủ công (sos_triggered)" },
    @{ kind = "event";       eventType = "sos_cancel";     label = "Tôi ổn — Hủy SOS (sos_cancel)" }
)

foreach ($action in $actions) {
    Write-Host "`n--- $($action.label) ---" -ForegroundColor Yellow
    if ($action.kind -eq "fall_event") {
        Invoke-Sim -Method POST -Path "/api/sim/events/fall" -Body @{
            device_id = $device.id
            event_type = "fall_detected"
            variant = $action.variant
        } | Out-Null
    } else {
        Invoke-Sim -Method POST -Path "/api/sim/events" -Body @{
            device_id = $device.id
            event_type = $action.eventType
        } | Out-Null
    }

    Start-Sleep -Milliseconds 600
    $fall = Invoke-Sim -Method GET -Path "/api/sim/sessions/$($session.id)/fall-state?device_id=$($device.id)"
    Write-Host ("  fallState = {0,-15} fallVariant = {1,-20} countdownRemainingSec = {2}" -f `
        $fall.fallState, ($fall.fallVariant ?? "—"), $fall.countdownRemainingSec)
}

Write-Host "`n[falllab-smoke] All buttons executed.  Inspect the printed fallState/fallVariant transitions to confirm BE responds correctly." -ForegroundColor Green
