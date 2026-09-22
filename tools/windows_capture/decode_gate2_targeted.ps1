param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Etl = Join-Path $OutRoot "gate2.etl"
$Markers = Join-Path $OutRoot "markers.tsv"
$Jsonl = Join-Path $OutRoot "gate2-targeted.jsonl"
$CountsCsv = Join-Path $OutRoot "gate2-targeted-counts.csv"
$WindowsCsv = Join-Path $OutRoot "gate2-targeted-windows.csv"
$Errors = Join-Path $OutRoot "gate2-targeted-errors.txt"

if (-not (Test-Path $Etl)) { throw "Missing ETL: $Etl" }
if (-not (Test-Path $Markers)) { throw "Missing markers: $Markers" }

$providers = [ordered]@{
    "dab01d4d-2d48-477d-b1c3-daad0ce6f06b" = "ACPI-Method"
    "c514638f-7723-485b-bcfc-96565d735d4a" = "Kernel-Acpi"
    "331c3b3a-2005-44c2-ac5e-77220c37d6b4" = "Kernel-Power"
    "9c205a39-1250-487d-abd7-e831c6290539" = "Kernel-PnP"
    "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716" = "Kernel-Process"
    "72cd9ff7-4af8-4b89-aede-5f26fda13567" = "SPB"
    "55ab77f6-fa04-43ef-af45-688fbf500482" = "GPIO"
    "6465da78-e7a0-4f39-b084-8f53c7c30dc6" = "HIDCLASS"
    "2fea7205-b0b1-41ca-8609-5a1d16f3132f" = "HidMini"
    "3fa102e9-1a62-5490-7af8-6088c2f9e6be" = "TouchAndPen"
}

function Normalize-Guid([object]$Value) {
    if ($null -eq $Value) { return "" }
    return ([string]$Value).Trim().Trim('{','}').ToLowerInvariant()
}

function Normalize-Value([object]$Value) {
    if ($null -eq $Value) { return $null }

    if ($Value -is [byte[]]) {
        $bytes = [byte[]]$Value
        $take = [Math]::Min($bytes.Length, 512)
        if ($take -gt 0) {
            $head = -join ($bytes[0..($take-1)] | ForEach-Object { $_.ToString("x2") })
        } else {
            $head = ""
        }

        return [ordered]@{
            kind = "bytes"
            length = $bytes.Length
            hex_head = $head
            truncated = ($bytes.Length -gt $take)
        }
    }

    if ($Value -is [Array]) {
        $items = @()
        foreach ($item in $Value) {
            if ($items.Count -ge 64) { break }
            $items += Normalize-Value $item
        }
        return [ordered]@{
            kind = "array"
            count = $Value.Count
            items = $items
            truncated = ($Value.Count -gt $items.Count)
        }
    }

    $s = [string]$Value
    if ($s.Length -gt 4096) {
        return [ordered]@{
            kind = "string"
            length = $s.Length
            text = $s.Substring(0,4096)
            truncated = $true
        }
    }
    return $s
}

$markerMap = @{}
foreach ($line in Get-Content $Markers) {
    if ($line -match '^\s*(\S+)\s+(\S+)(?:\s+(.*))?$') {
        try {
            $ts = [DateTimeOffset]::Parse($Matches[1]).ToUniversalTime()
            $markerMap[$Matches[2]] = $ts
        } catch {}
    }
}

$requiredMarkers = @(
    "T0_BOOTTRACE_ACTIVE",
    "T2_DISABLE_BEGIN",
    "T2_ENABLE_BEGIN",
    "T3_ONE_FINGER_BEGIN",
    "T3_ONE_FINGER_END",
    "T4_TWO_FINGER_BEGIN",
    "T4_TWO_FINGER_END",
    "T5_SLEEP_BEGIN",
    "T5_RESUME",
    "T5_POST_RESUME_ONE_FINGER_BEGIN",
    "T5_POST_RESUME_ONE_FINGER_END",
    "T6_STOP"
)
$missingMarkers = @($requiredMarkers | Where-Object { -not $markerMap.ContainsKey($_) })
if ($missingMarkers.Count -gt 0) {
    throw "Missing required markers: $($missingMarkers -join ', ')"
}

$first = Get-WinEvent -Path $Etl -Oldest -MaxEvents 1 -ErrorAction Stop
$etlStart = ([DateTimeOffset]$first.TimeCreated).ToUniversalTime()

$windows = @(
    [pscustomobject]@{ name="COLD_BOOT"; start=$etlStart; end=$markerMap["T0_BOOTTRACE_ACTIVE"].AddSeconds(2) },
    [pscustomobject]@{ name="T2_DISABLE_ENABLE"; start=$markerMap["T2_DISABLE_BEGIN"].AddSeconds(-1); end=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.1) },
    [pscustomobject]@{ name="T3_ONE_FINGER"; start=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.5); end=$markerMap["T3_ONE_FINGER_END"].AddSeconds(0.5) },
    [pscustomobject]@{ name="T4_TWO_FINGER"; start=$markerMap["T4_TWO_FINGER_BEGIN"].AddSeconds(-0.5); end=$markerMap["T4_TWO_FINGER_END"].AddSeconds(0.5) },
    [pscustomobject]@{ name="T5_SLEEP_RESUME"; start=$markerMap["T5_SLEEP_BEGIN"].AddSeconds(-1); end=$markerMap["T5_RESUME"].AddSeconds(2) },
    [pscustomobject]@{ name="T5_POST_RESUME_FINGER"; start=$markerMap["T5_POST_RESUME_ONE_FINGER_BEGIN"].AddSeconds(-0.5); end=$markerMap["T5_POST_RESUME_ONE_FINGER_END"].AddSeconds(0.5) }
)

$windows | Select-Object name,start,end | Export-Csv -NoTypeInformation -Encoding utf8 $WindowsCsv

$providerCounts = @{}
$windowCounts = @{}
foreach ($name in $providers.Values) { $providerCounts[$name] = 0 }
foreach ($w in $windows) {
    foreach ($name in $providers.Values) {
        $windowCounts["$($w.name)|$name"] = 0
    }
}

Remove-Item -Force -ErrorAction SilentlyContinue $Jsonl,$Errors
$writer = [System.IO.StreamWriter]::new($Jsonl,$false,[System.Text.UTF8Encoding]::new($false))

try {
    $readErrors = @()
    Get-WinEvent -Path $Etl -Oldest -ErrorAction SilentlyContinue -ErrorVariable +readErrors | ForEach-Object {
        $e = $_
        $guid = Normalize-Guid $e.ProviderId
        if (-not $providers.Contains($guid)) { return }

        $providerName = $providers[$guid]
        $providerCounts[$providerName]++

        $t = ([DateTimeOffset]$e.TimeCreated).ToUniversalTime()
        $windowNames = @()
        foreach ($w in $windows) {
            if ($t -ge $w.start -and $t -le $w.end) {
                $windowNames += $w.name
                $windowCounts["$($w.name)|$providerName"]++
            }
        }

        if ($windowNames.Count -eq 0) { return }

        $props = @()
        foreach ($p in @($e.Properties)) {
            $props += Normalize-Value $p.Value
        }

        $msg = $null
        try { $msg = $e.FormatDescription() } catch {}
        if ($null -ne $msg -and $msg.Length -gt 8192) {
            $msg = $msg.Substring(0,8192)
        }

        $record = [ordered]@{
            status = "OBSERVED"
            time_utc = $t.ToString("o")
            windows = $windowNames
            provider = $providerName
            provider_guid = $guid
            event_id = $e.Id
            version = $e.Version
            level = $e.LevelDisplayName
            task = $e.TaskDisplayName
            opcode = $e.OpcodeDisplayName
            process_id = $e.ProcessId
            thread_id = $e.ThreadId
            record_id = $e.RecordId
            properties = $props
            message = $msg
        }

        $writer.WriteLine(($record | ConvertTo-Json -Depth 8 -Compress))
    }

    if ($readErrors.Count -gt 0) {
        $readErrors | Out-String -Width 500 | Set-Content -Encoding utf8 $Errors
    }
} finally {
    $writer.Dispose()
}

$rows = foreach ($guid in $providers.Keys) {
    $name = $providers[$guid]
    [pscustomobject]@{
        provider = $name
        guid = $guid
        total_events = [int64]$providerCounts[$name]
        cold_boot = [int64]$windowCounts["COLD_BOOT|$name"]
        t2_disable_enable = [int64]$windowCounts["T2_DISABLE_ENABLE|$name"]
        t3_one_finger = [int64]$windowCounts["T3_ONE_FINGER|$name"]
        t4_two_finger = [int64]$windowCounts["T4_TWO_FINGER|$name"]
        t5_sleep_resume = [int64]$windowCounts["T5_SLEEP_RESUME|$name"]
        t5_post_resume_finger = [int64]$windowCounts["T5_POST_RESUME_FINGER|$name"]
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding utf8 $CountsCsv
$rows | Format-Table -AutoSize | Out-String -Width 260 | Write-Host

$required = @("ACPI-Method","Kernel-Acpi","Kernel-Power","Kernel-PnP","Kernel-Process","SPB","GPIO","HIDCLASS")
$missingProviders = @($required | Where-Object { $providerCounts[$_] -eq 0 })
if ($missingProviders.Count -gt 0) {
    Write-Host ""
    Write-Host ("TARGETED COVERAGE FAIL: " + ($missingProviders -join ", "))
    exit 2
}

Write-Host ""
Write-Host "TARGETED COVERAGE PASS"
Write-Host ("ETL: " + $Etl)
Write-Host ("JSONL: " + $Jsonl)
Write-Host ("Counts: " + $CountsCsv)
