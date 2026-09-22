param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$session = "WPR_initiated_WprApp_boottr_TouchInitCollector"
$key = "HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\$session"
$keyNative = "HKLM\SYSTEM\CurrentControlSet\Control\WMI\Autologger\$session"
$out = Join-Path $OutRoot "boottrace-diagnose.txt"

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$s="") {
    $lines.Add($s)
    Write-Host $s
}

Add-Line "=== GATE 2 BOOTTRACE DIAG ==="
Add-Line ("UTC: " + [DateTimeOffset]::UtcNow.ToString("o"))
Add-Line ""

Add-Line "=== WPR STATUS ==="
$wpr = (& wpr.exe -status profiles collectors -details 2>&1 | Out-String -Width 500)
Add-Line $wpr

Add-Line "=== AUTOLOGGER REGISTRY ==="
if (Test-Path $key) {
    Add-Line ("PRESENT: " + $keyNative)
    $props = Get-ItemProperty -Path $key
    foreach ($name in @("Start","Status","Guid","FileName","LogFileMode","BufferSize","MinimumBuffers","MaximumBuffers","MaxFileSize","FlushTimer","ClockType","Boot")) {
        $p = $props.PSObject.Properties[$name]
        if ($null -ne $p) {
            Add-Line ("{0}={1}" -f $name,$p.Value)
        }
    }
} else {
    Add-Line ("MISSING: " + $keyNative)
}

Add-Line ""
Add-Line "=== ACTIVE ETW SESSIONS (LOGMAN -ETS) ==="
$ets = (& logman.exe query -ets 2>&1 | Out-String -Width 500)
Add-Line $ets
if ($ets -match [regex]::Escape($session)) {
    Add-Line "RESULT: TouchInitCollector IS ACTIVE in ETW."
} else {
    Add-Line "RESULT: TouchInitCollector is NOT ACTIVE in ETW."
}

Add-Line ""
Add-Line "=== TEMP TRACE FILE ==="
$temp = Join-Path $OutRoot "wpr-temp\$session.etl"
if (Test-Path $temp) {
    $a = Get-Item $temp
    Add-Line ("PRESENT: {0} bytes={1} LastWrite={2:o}" -f $a.FullName,$a.Length,$a.LastWriteTimeUtc)
    Start-Sleep -Seconds 3
    $b = Get-Item $temp
    Add-Line ("AFTER 3s: bytes={0} LastWrite={1:o}" -f $b.Length,$b.LastWriteTimeUtc)
    if ($b.Length -gt $a.Length -or $b.LastWriteTimeUtc -gt $a.LastWriteTimeUtc) {
        Add-Line "RESULT: temp ETL is growing/changing."
    } else {
        Add-Line "RESULT: temp ETL is not growing during this sample."
    }
} else {
    Add-Line ("MISSING: " + $temp)
}

Add-Line ""
Add-Line "=== KERNEL-EVENTTRACING RECENT ERRORS/WARNINGS ==="
try {
    $since = (Get-Date).AddHours(-2)
    $events = Get-WinEvent -FilterHashtable @{
        LogName='Microsoft-Windows-Kernel-EventTracing/Admin'
        StartTime=$since
        Level=1,2,3
    } -ErrorAction Stop | Select-Object -First 50
    if ($events) {
        foreach ($e in $events) {
            Add-Line ("[{0:o}] ID={1} Level={2} {3}" -f $e.TimeCreated,$e.Id,$e.LevelDisplayName,($e.Message -replace "\r?\n"," "))
        }
    } else {
        Add-Line "No recent warning/error events."
    }
} catch {
    Add-Line ("Could not read Kernel-EventTracing/Admin: " + $_.Exception.Message)
}

Add-Line ""
Add-Line "=== PROVIDER SUBKEY COUNT ==="
if (Test-Path $key) {
    $subs = @(Get-ChildItem -Path $key -ErrorAction SilentlyContinue)
    Add-Line ("provider_subkeys=" + $subs.Count)
}

$lines | Set-Content -Encoding utf8 $out
Write-Host ""
Write-Host "Saved: $out"
