# Phase 3 smoke test — re-run with /api/v1/sim/ prefix and assert
# preTriggerResult is populated for all 6 variants.
#
# Usage:
#   pwsh scripts/phase3_smoke.ps1 -SessionId <id> -DeviceId <id>

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
        $resp = Invoke-WebRequest -Uri "$SimBaseUrl/api/v1/sim/events/fall" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 10
        return $resp.StatusCode
    } catch { return "ERR: $($_.Exception.Message)" }
}

function Invoke-Cancel {
    $body = @{ device_id = $DeviceId; event_type = "sos_cancel" } | ConvertTo-Json -Compress
    try {
        Invoke-WebRequest -Uri "$SimBaseUrl/api/v1/sim/events" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 5 | Out-Null
    } catch { }
}

function Get-FallState {
    $url = "$SimBaseUrl/api/v1/sim/sessions/$SessionId/fall-state?deviceId=$DeviceId"
    return (Invoke-WebRequest -Uri $url -UseBasicParsing).Content | ConvertFrom-Json
}

# ---------------------------------------------------------------------------
# Pre-check: model-api up?
# ---------------------------------------------------------------------------
Write-Host "`n=== Pre-check: model-api ===" -ForegroundColor Cyan
try {
    $info = (Invoke-WebRequest -Uri "$ModelApiUrl/api/v1/fall/model-info" -UseBasicParsing).Content | ConvertFrom-Json
    Write-Host ("model_name={0} status={1}" -f $info.model_name, $info.status)
} catch {
    Write-Host "Model API unreachable" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Variants — adds expectedPreTrigger (Phase 2)
# ---------------------------------------------------------------------------
$variants = @(
    @{ id = "false_fall";       expDevState = "streaming";      expCountdown = 0;  expPreTrig = "none" },
    @{ id = "slip_recovery";    expDevState = "streaming";      expCountdown = 0;  expPreTrig = "none" },
    @{ id = "fall_brief";       expDevState = "fall_countdown"; expCountdown = 10; expPreTrig = "soft" },
    @{ id = "fall_from_bed";    expDevState = "fall_countdown"; expCountdown = 30; expPreTrig = "soft" },
    @{ id = "confirmed";        expDevState = "fall_countdown"; expCountdown = 30; expPreTrig = "hard" },
    @{ id = "fall_no_response"; expDevState = "fall_countdown"; expCountdown = 30; expPreTrig = "hard" }
)

foreach ($v in $variants) {
    Write-Host "`n=== Variant: $($v.id) ===" -ForegroundColor Cyan
    Invoke-Cancel
    Start-Sleep -Milliseconds 300
    $status = Invoke-Inject -Variant $v.id
    Write-Host ("inject HTTP={0}" -f $status)
    Start-Sleep -Milliseconds 1000
    $state = Get-FallState

    $aiOk = $state.aiPrediction -ne $null
    $aiStatus = if ($aiOk) { $state.aiPrediction.modelStatus } else { "null" }
    $aiLabel = if ($aiOk) { $state.aiPrediction.label } else { "null" }
    $aiBand = if ($aiOk) { $state.aiPrediction.riskBand } else { "null" }
    $aiProb = if ($aiOk) { [math]::Round($state.aiPrediction.probability * 100, 1) } else { 0 }

    $preTrig = $state.preTriggerResult
    $preTrigType = if ($preTrig) { $preTrig.triggerType } else { "null" }
    $preTrigPeak = if ($preTrig -and $preTrig.accelPeakG) { [math]::Round($preTrig.accelPeakG, 2) } else { "null" }
    $preTrigCodes = if ($preTrig) { ($preTrig.reasonCodes -join ",") } else { "null" }

    $deviceStateOk = $state.deviceState -eq $v.expDevState
    $countdownOk = $state.countdownTotalSec -eq $v.expCountdown
    $preTrigOk = $preTrigType -eq $v.expPreTrig
    $verdict = if ($deviceStateOk -and $countdownOk -and $preTrigOk) { "PASS" } else { "FAIL" }

    Write-Host ("  deviceState={0} (expected {1}) {2}" -f $state.deviceState, $v.expDevState, $(if ($deviceStateOk) { "OK" } else { "X" }))
    Write-Host ("  countdownTotalSec={0} (expected {1}) {2}" -f $state.countdownTotalSec, $v.expCountdown, $(if ($countdownOk) { "OK" } else { "X" }))
    Write-Host ("  preTriggerResult: type={0} (expected {1}) peak={2}g codes=[{3}] {4}" -f $preTrigType, $v.expPreTrig, $preTrigPeak, $preTrigCodes, $(if ($preTrigOk) { "OK" } else { "X" }))
    Write-Host ("  AI: status={0} label={1} band={2} prob={3}%" -f $aiStatus, $aiLabel, $aiBand, $aiProb)

    $summary += [PSCustomObject]@{
        Variant = $v.id
        DeviceState = $(if ($deviceStateOk){'OK'}else{"X $($state.deviceState)"})
        Countdown = "$($state.countdownTotalSec)s$(if($countdownOk){' OK'}else{' X'})"
        PreTrig = "$preTrigType$(if($preTrigOk){' OK'}else{" X exp=$($v.expPreTrig)"})"
        AccelPeak = "$preTrigPeak g"
        AIBand = $aiBand
        AIProb = "$aiProb%"
        Verdict = $verdict
    }
}

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
