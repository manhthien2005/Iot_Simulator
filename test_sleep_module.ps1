# test_sleep_module.ps1
# Tests sleep module by pushing all 6 scenarios for past dates,
# then comparing actual BE response vs expected targets from
# config/sleepScenarios.ts and api_server/config/sleep_scenarios.yaml.

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8092/api/v1/sim"

# Pick first bound, online device
$devices = Invoke-RestMethod -Uri "$base/devices"
$device = $devices | Where-Object { $_.boundDbDeviceId -ne $null -and $_.isOnline } | Select-Object -First 1
if (-not $device) { throw "No bound device found" }
Write-Host "[setup] Device: $($device.name) ($($device.id)), bound to db_id=$($device.boundDbDeviceId)" -ForegroundColor Cyan

# Expected targets — mirror config/sleepScenarios.ts
$expected = @(
    @{ id="good_sleep_night";   eff=0.95; deep=0.18; rem=0.22; awake=0.05; wake=1;  spo2=$null;  severity="normal"  }
    @{ id="fragmented_sleep";   eff=0.79; deep=0.10; rem=0.14; awake=0.21; wake=4;  spo2=$null;  severity="warning" }
    @{ id="sleep_apnea_mild";   eff=0.76; deep=0.10; rem=0.15; awake=0.24; wake=8;  spo2=91;     severity="warning" }
    @{ id="sleep_apnea_severe"; eff=0.62; deep=0.05; rem=0.08; awake=0.38; wake=18; spo2=84;     severity="critical"}
    @{ id="insomnia_pattern";   eff=0.63; deep=0.08; rem=0.12; awake=0.37; wake=6;  spo2=$null;  severity="warning" }
    @{ id="elderly_normal";     eff=0.80; deep=0.11; rem=0.19; awake=0.20; wake=2;  spo2=$null;  severity="normal"  }
)

# Push each scenario for a unique past date (T-2 .. T-7)
$results = @()
for ($i = 0; $i -lt $expected.Count; $i++) {
    $sc = $expected[$i]
    $date = (Get-Date).AddDays(-2 - $i).ToString("yyyy-MM-dd")
    $body = @{
        device_id = $device.id
        target_date = $date
        scenario_id = $sc.id
    } | ConvertTo-Json
    Write-Host "[push] $($sc.id) -> $date" -ForegroundColor Yellow
    try {
        $resp = Invoke-RestMethod -Uri "$base/scenarios/sleep/push-date" -Method Post -Body $body -ContentType "application/json"
        $results += [PSCustomObject]@{
            scenario   = $sc.id
            date       = $date
            score      = $resp.sleep_score
            durationMin= $resp.duration_minutes
            tags       = ($resp.disorder_tags -join ",")
            ok         = $resp.success
            overwrite  = $resp.was_overwritten
            expEff     = $sc.eff
            expDeep    = $sc.deep
            expWake    = $sc.wake
            expSpO2    = $sc.spo2
        }
    } catch {
        Write-Host "  ERR: $_" -ForegroundColor Red
    }
    Start-Sleep -Milliseconds 500
}

Write-Host "`n=== PUSH RESULTS ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize

# Pull saved DB rows back and compare
Write-Host "`n=== DB HISTORY (from /analytics/sleep/history) ===" -ForegroundColor Cyan
$history = Invoke-RestMethod -Uri "$base/analytics/sleep/history?deviceId=$($device.id)&days=30"
$historyByDate = @{}
foreach ($row in $history) { $historyByDate[$row.date] = $row }

$compare = @()
foreach ($r in $results) {
    $row = $historyByDate[$r.date]
    if (-not $row) {
        $compare += [PSCustomObject]@{ scenario=$r.scenario; date=$r.date; status="NOT IN DB" }
        continue
    }
    $totalMin = $row.durationMinutes
    $awakeMin = if ($row.phases.awake) { $row.phases.awake } else { 0 }
    $deepMin  = if ($row.phases.deep) { $row.phases.deep } else { 0 }
    $remMin   = if ($row.phases.rem) { $row.phases.rem } else { 0 }
    $deepPct  = if ($totalMin -gt 0) { [math]::Round($deepMin / $totalMin, 3) } else { 0 }
    $awakePct = if ($totalMin -gt 0) { [math]::Round($awakeMin / $totalMin, 3) } else { 0 }
    $remPct   = if ($totalMin -gt 0) { [math]::Round($remMin / $totalMin, 3) } else { 0 }
    $effPct   = [math]::Round($row.efficiency / 100, 3)

    $compare += [PSCustomObject]@{
        scenario  = $r.scenario
        date      = $r.date
        score     = $row.score
        durMin    = $totalMin
        eff       = $effPct
        expEff    = $r.expEff
        deepPct   = $deepPct
        expDeep   = $r.expDeep
        remPct    = $remPct
        awakePct  = $awakePct
        wake      = $row.wakeCount
        expWake   = $r.expWake
    }
}
$compare | Format-Table -AutoSize

# Summary deltas
Write-Host "`n=== DELTA vs CONFIG ===" -ForegroundColor Cyan
foreach ($c in $compare) {
    if ($c.PSObject.Properties.Name -contains "status") {
        Write-Host ("[{0}] {1}" -f $c.scenario, $c.status) -ForegroundColor Red
        continue
    }
    $effDelta  = [math]::Round($c.eff - $c.expEff, 3)
    $deepDelta = [math]::Round($c.deepPct - $c.expDeep, 3)
    $color = "Green"
    if ([math]::Abs($effDelta) -gt 0.10 -or [math]::Abs($deepDelta) -gt 0.08) { $color = "Yellow" }
    if ([math]::Abs($effDelta) -gt 0.20 -or [math]::Abs($deepDelta) -gt 0.15) { $color = "Red" }
    Write-Host ("[{0}] eff={1:F2} (Δ{2:+0.00;-0.00;0.00}) deep={3:F2} (Δ{4:+0.00;-0.00;0.00}) wake={5} (exp {6}) score={7}" -f
        $c.scenario, $c.eff, $effDelta, $c.deepPct, $deepDelta, $c.wake, $c.expWake, $c.score) -ForegroundColor $color
}
