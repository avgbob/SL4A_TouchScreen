param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Etl = Join-Path $OutRoot "gate2.etl"
$Evtx = Join-Path $OutRoot "gate2.evtx"
$Markers = Join-Path $OutRoot "markers.tsv"
$Jsonl = Join-Path $OutRoot "gate2-windowed.jsonl"
$CountsCsv = Join-Path $OutRoot "gate2-windowed-counts.csv"
$WindowsCsv = Join-Path $OutRoot "gate2-windowed-windows.csv"

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
        $take = [Math]::Min($bytes.Length, 2048)
        $head = ""
        if ($take -gt 0) {
            $head = -join ($bytes[0..($take-1)] | ForEach-Object { $_.ToString("x2") })
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
            if ($items.Count -ge 128) { break }
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
    if ($s.Length -gt 8192) {
        return [ordered]@{
            kind = "string"
            length = $s.Length
            text = $s.Substring(0,8192)
            truncated = $true
        }
    }
    return $s
}

# Convert once using native tracerpt. EVTX is compact and queryable.
$needConvert = (-not (Test-Path $Evtx)) -or ((Get-Item $Evtx).LastWriteTimeUtc -lt (Get-Item $Etl).LastWriteTimeUtc)
if ($needConvert) {
    Write-Host "Converting ETL -> EVTX once..."
    & tracerpt.exe $Etl -o $Evtx -of EVTX -lr -y
    if ($LASTEXITCODE -ne 0) {
        throw "tracerpt ETL->EVTX failed with code $LASTEXITCODE"
    }
} else {
    Write-Host "Using existing EVTX: $Evtx"
}

$markerMap = @{}
foreach ($line in Get-Content $Markers) {
    if ($line -match '^\s*(\S+)\s+(\S+)(?:\s+(.*))?$') {
        try {
            $markerMap[$Matches[2]] = [DateTimeOffset]::Parse($Matches[1]).ToUniversalTime()
        } catch {}
    }
}

$needed = @(
    "T0_BOOTTRACE_ACTIVE",
    "T2_DISABLE_BEGIN",
    "T3_ONE_FINGER_BEGIN",
    "T3_ONE_FINGER_END",
    "T4_TWO_FINGER_BEGIN",
    "T4_TWO_FINGER_END",
    "T5_SLEEP_BEGIN",
    "T5_RESUME",
    "T5_POST_RESUME_ONE_FINGER_BEGIN",
    "T5_POST_RESUME_ONE_FINGER_END"
)
$missing = @($needed | Where-Object { -not $markerMap.ContainsKey($_) })
if ($missing.Count -gt 0) {
    throw "Missing markers: $($missing -join ', ')"
}

$first = Get-WinEvent -Path $Evtx -Oldest -MaxEvents 1
$etlStart = ([DateTimeOffset]$first.TimeCreated).ToUniversalTime()

$windows = @(
    [pscustomobject]@{ Name="COLD_BOOT"; Start=$etlStart; End=$markerMap["T0_BOOTTRACE_ACTIVE"].AddSeconds(2) },
    [pscustomobject]@{ Name="T2_DISABLE_ENABLE"; Start=$markerMap["T2_DISABLE_BEGIN"].AddSeconds(-1); End=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.1) },
    [pscustomobject]@{ Name="T3_ONE_FINGER"; Start=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T3_ONE_FINGER_END"].AddSeconds(0.5) },
    [pscustomobject]@{ Name="T4_TWO_FINGER"; Start=$markerMap["T4_TWO_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T4_TWO_FINGER_END"].AddSeconds(0.5) },
    [pscustomobject]@{ Name="T5_SLEEP_RESUME"; Start=$markerMap["T5_SLEEP_BEGIN"].AddSeconds(-1); End=$markerMap["T5_RESUME"].AddSeconds(2) },
    [pscustomobject]@{ Name="T5_POST_RESUME_FINGER"; Start=$markerMap["T5_POST_RESUME_ONE_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T5_POST_RESUME_ONE_FINGER_END"].AddSeconds(0.5) }
)
$windows | Export-Csv -NoTypeInformation -Encoding utf8 $WindowsCsv

$providerClause = ($providers.Keys | ForEach-Object { "Provider[@Guid='{" + $_ + "}']" }) -join " or "

Remove-Item -Force -ErrorAction SilentlyContinue $Jsonl,$CountsCsv
$writer = [System.IO.StreamWriter]::new($Jsonl,$false,[System.Text.UTF8Encoding]::new($false))
$counts = @{}
foreach ($w in $windows) {
    foreach ($p in $providers.Values) {
        $counts["$($w.Name)|$p"] = 0L
    }
}

try {
    $wi = 0
    foreach ($w in $windows) {
        $wi++
        $startIso = $w.Start.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ")
        $endIso = $w.End.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ")
        $xpath = "*[System[(($providerClause)) and TimeCreated[@SystemTime >= '$startIso' and @SystemTime <= '$endIso']]]"

        Write-Host ("[{0}/{1}] {2}: {3:o} -> {4:o}" -f $wi,$windows.Count,$w.Name,$w.Start,$w.End)
        $n = 0L

        Get-WinEvent -Path $Evtx -FilterXPath $xpath -Oldest -ErrorAction SilentlyContinue | ForEach-Object {
            $e = $_
            $guid = Normalize-Guid $e.ProviderId
            if (-not $providers.Contains($guid)) { return }

            $providerName = $providers[$guid]
            $counts["$($w.Name)|$providerName"]++
            $n++

            $props = @()
            foreach ($p in @($e.Properties)) {
                $props += Normalize-Value $p.Value
            }

            $msg = $null
            # Formatting high-volume SPB/GPIO/HIDCLASS records is expensive
            # and their raw Properties are the evidence we need.
            if ($providerName -notin @("SPB","GPIO","HIDCLASS","Kernel-Process")) {
                try { $msg = $e.FormatDescription() } catch {}
                if ($null -ne $msg -and $msg.Length -gt 8192) {
                    $msg = $msg.Substring(0,8192)
                }
            }

            $record = [ordered]@{
                status = "OBSERVED"
                window = $w.Name
                time_utc = ([DateTimeOffset]$e.TimeCreated).ToUniversalTime().ToString("o")
                provider = $providerName
                provider_guid = $guid
                provider_name = $e.ProviderName
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

        Write-Host ("    extracted {0} target events" -f $n)
    }
} finally {
    $writer.Dispose()
}

$rows = foreach ($w in $windows) {
    foreach ($p in $providers.Values) {
        [pscustomobject]@{
            window = $w.Name
            provider = $p
            events = [int64]$counts["$($w.Name)|$p"]
        }
    }
}
$rows | Export-Csv -NoTypeInformation -Encoding utf8 $CountsCsv
$rows | Where-Object events -gt 0 | Format-Table -AutoSize | Out-String -Width 180 | Write-Host

Write-Host ""
Write-Host "WINDOWED DECODE COMPLETE"
Write-Host ("EVTX: " + $Evtx)
Write-Host ("JSONL: " + $Jsonl)
Write-Host ("Counts: " + $CountsCsv)
