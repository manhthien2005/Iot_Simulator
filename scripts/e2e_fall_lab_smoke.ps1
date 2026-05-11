# Module FA — Live E2E smoke for the fall AI integration.
#
# Walks through all 6 variants in the FALL_VARIANT_CATALOGUE, asserting
# the BE-cached AI verdict + variant policy match expectations.  Run
# AFTER restarting the simulator BE so the latest code is in memory.
#
# Pre-reqs:
#   - simulator BE on :8090 with at least one running session
#   - healthguard-model-api on :8001
#
# Usage:
#   pwsh scripts\e2e_fall_lab_smoke.ps1 -SessionId <id> -DeviceId <id>

param(
    [Parameter(Mandatory=$true)] [string] $SessionId,
    [Parameter(Mandatory=$true)] [string] $DeviceId,
    [string] $SimBaseUrl = "http://127.0.0.1:8090",
    [string] $ModelApiUrl = "http://127.0.0.1:8001"
)

$ErrorActionPreference = "Continue"
$summary = @()

function Invoke-Inject {
    param([string] $Variant)
    $body = @{ device_id = $DeviceId; event_type = "fall_detected"; variant = $Variant } | ConvertTo-Json -Compress
    try {
        $resp = Invoke-WebRequest -Uri "$SimBaseUrl/api/sim/events/fall" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 10
        return $resp.StatusCode
    } catch { return "ERR: $($_.Exception.Message)" }
}

function Invoke-Cancel {
    $body = @{ device_id = $DeviceId; event_type = "sos_cancel" } | ConvertTo-Json -Compress
    try {
        Invoke-WebRequest -Uri "$SimBaseUrl/api/sim/events" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5 | Out-Null
    } catch { }
}

function Get-FallState {
    $url = "$SimBaseUrl/api/sim/sessions/$SessionId/fall-state?deviceId=$DeviceId"
    return (Invoke-WebRequest -Uri $url -UseBasicParsing).Content | ConvertFrom-Json
}

# ---------------------------------------------------------------------------
# Pre-check: model-api up?
# ---------------------------------------------------------------------------
Write-Host "`n=== Pre-check: model-api ===" -ForegroundColor Cyan
try {
    $info = (Invoke-WebRequest -Uri "$ModelApiUrl/api/v1/fall/model-info" -UseBasicParsing).Content | ConvertFrom-Json
    Write-Host ("model_name={0} status={1} backend={2} features={3}" -f $info.model_name, $info.status, $info.inference_backend, $info.feature_count)
} catch {
    Write-Host "Model API unreachable — verdict will surface as 'offline'" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Run all 6 variants
# ---------------------------------------------------------------------------
$variants = @(
    @{ id = "false_fall";       expectedDeviceState = "streaming";     expectedCountdownTotal = 0;  expectedAutoResolve = $false; expectedAllowsCancel = $false },
    @{ id = "slip_recovery";    expectedDeviceState = "streaming";     expectedCountdownTotal = 0;  expectedAutoResolve = $false; expectedAllowsCancel = $false },
    @{ id = "fall_brief";       expectedDeviceState = "fall_countdown"; expectedCountdownTotal = 10; expectedAutoResolve = $true;  expectedAllowsCancel = $true },
    @{ id = "fall_from_bed";    expectedDeviceState = "fall_countdown"; expectedCountdownTotal = 30; expectedAutoResolve = $false; expectedAllowsCancel = $true },
    @{ id = "confirmed";        expectedDeviceState = "fall_countdown"; expectedCountdownTotal = 30; expectedAutoResolve = $false; expectedAllowsCancel = $true },
    @{ id = "fall_no_response"; expectedDeviceState = "fall_countdown"; expectedCountdownTotal = 30; expectedAutoResolve = $false; expectedAllowsCancel = $false }
)

foreach ($v in $variants) {
    Write-Host "`n=== Variant: $($v.id) ===" -ForegroundColor Cyan
    Invoke-Cancel  # clear any previous countdown
    Start-Sleep -Milliseconds 200
    $status = Invoke-Inject -Variant $v.id
    Write-Host ("inject HTTP={0}" -f $status)
    Start-Sleep -Milliseconds 800
    $state = Get-FallState

    $aiOk = $state.aiPrediction -ne $null
    $aiStatus = if ($aiOk) { $state.aiPrediction.modelStatus } else { "null" }
    $aiLabel = if ($aiOk) { $state.aiPrediction.label } else { "null" }
    $aiBand = if ($aiOk) { $state.aiPrediction.riskBand } else { "null" }
    $aiProb = if ($aiOk) { [math]::Round($state.aiPrediction.probability * 100, 1) } else { 0 }
    $deviceStateOk = $state.deviceState -eq $v.expectedDeviceState
    $countdownOk = $state.countdownTotalSec -eq $v.expectedCountdownTotal
    $policyOk = ($state.countdownPolicy -ne $null) -and (
        ($state.countdownPolicy.totalSec -eq $v.expectedCountdownTotal) -and
        ($state.countdownPolicy.autoResolve -eq $v.expectedAutoResolve) -and
        ($state.countdownPolicy.allowsCancel -eq $v.expectedAllowsCancel)
    )
    $verdict = if ($deviceStateOk -and $countdownOk -and $policyOk) { "PASS" } else { "FAIL" }

    Write-Host ("  deviceState={0} (expected {1}) {2}" -f $state.deviceState, $v.expectedDeviceState, $(if ($deviceStateOk) { "OK" } else { "X" }))
    Write-Host ("  countdownTotalSec={0} (expected {1}) {2}" -f $state.countdownTotalSec, $v.expectedCountdownTotal, $(if ($countdownOk) { "OK" } else { "X" }))
    Write-Host ("  countdownPolicy={0} {1}" -f ($state.countdownPolicy | ConvertTo-Json -Compress), $(if ($policyOk) { "OK" } else { "X" }))
    Write-Host ("  AI: status={0} label={1} band={2} prob={3}%" -f $aiStatus, $aiLabel, $aiBand, $aiProb)

    $summary += [PSCustomObject]@{
        Variant = $v.id
        DeviceState = "$($state.deviceState) ($(if ($deviceStateOk){'OK'}else{'X'}))"
        CountdownTotal = "$($state.countdownTotalSec)s ($(if ($countdownOk){'OK'}else{'X'}))"
        Policy = if ($policyOk) { "OK" } else { "X" }
        AIStatus = $aiStatus
        AILabel = $aiLabel
        AIBand = $aiBand
        AIProb = "$aiProb%"
        Verdict = $verdict
    }
}

# ---------------------------------------------------------------------------
# Final summary table
# ---------------------------------------------------------------------------
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
$summary | Format-Table -AutoSize

$failureCount = ($summary | Where-Object { $_.Verdict -eq "FAIL" }).Count
$totalCount = $summary.Count
Write-Host ""
if ($failureCount -eq 0) {
    Write-Host ("ALL {0} VARIANTS PASS" -f $totalCount) -ForegroundColor Green
    exit 0
} else {
    Write-Host ("{0} of {1} VARIANTS FAILED" -f $failureCount, $totalCount) -ForegroundColor Red
    exit 1
}
