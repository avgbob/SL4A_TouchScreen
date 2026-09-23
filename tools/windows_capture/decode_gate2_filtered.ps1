param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Etl = Join-Path $OutRoot "gate2.etl"
$Markers = Join-Path $OutRoot "markers.tsv"
$Jsonl = Join-Path $OutRoot "gate2-filtered.jsonl"
$CountsCsv = Join-Path $OutRoot "gate2-filtered-counts.csv"
$WindowsCsv = Join-Path $OutRoot "gate2-filtered-windows.csv"

if (-not (Test-Path $Etl)) { throw "Missing ETL: $Etl" }
if (-not (Test-Path $Markers)) { throw "Missing markers: $Markers" }

$providers = @(
    [pscustomobject]@{ Name="ACPI-Method"; Guid="dab01d4d-2d48-477d-b1c3-daad0ce6f06b"; IncludeMessage=$true },
    [pscustomobject]@{ Name="Kernel-Acpi"; Guid="c514638f-7723-485b-bcfc-96565d735d4a"; IncludeMessage=$true },
    [pscustomobject]@{ Name="Kernel-Power"; Guid="331c3b3a-2005-44c2-ac5e-77220c37d6b4"; IncludeMessage=$true },
    [pscustomobject]@{ Name="Kernel-PnP"; Guid="9c205a39-1250-487d-abd7-e831c6290539"; IncludeMessage=$true },
    [pscustomobject]@{ Name="Kernel-Process"; Guid="22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"; IncludeMessage=$false },
    [pscustomobject]@{ Name="SPB"; Guid="72cd9ff7-4af8-4b89-aede-5f26fda13567"; IncludeMessage=$false },
    [pscustomobject]@{ Name="GPIO"; Guid="55ab77f6-fa04-43ef-af45-688fbf500482"; IncludeMessage=$false },
    [pscustomobject]@{ Name="HIDCLASS"; Guid="6465da78-e7a0-4f39-b084-8f53c7c30dc6"; IncludeMessage=$false },
    [pscustomobject]@{ Name="HidMini"; Guid="2fea7205-b0b1-41ca-8609-5a1d16f3132f"; IncludeMessage=$true },
    [pscustomobject]@{ Name="TouchAndPen"; Guid="3fa102e9-1a62-5490-7af8-6088c2f9e6be"; IncludeMessage=$true }
)

function Normalize-Value([object]$Value) {
    if ($null -eq $Value) { return $null }

    if ($Value -is [byte[]]) {
        $bytes = [byte[]]$Value
        $take = [Math]::Min($bytes.Length, 1024)
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

$markerMap = @{}
foreach ($line in Get-Content $Markers) {
    if ($line -match '^\s*(\S+)\s+(\S+)(?:\s+(.*))?$') {
        try {
            $markerMap[$Matches[2]] = [DateTimeOffset]::Parse($Matches[1]).ToUniversalTime()
        } catch {}
    }
}

$neededMarkers = @(
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
$missingMarkers = @($neededMarkers | Where-Object { -not $markerMap.ContainsKey($_) })
if ($missingMarkers.Count -gt 0) {
    throw "Missing required markers: $($missingMarkers -join ', ')"
}

$first = Get-WinEvent -Path $Etl -Oldest -MaxEvents 1
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

Remove-Item -Force -ErrorAction SilentlyContinue $Jsonl,$CountsCsv
$writer = [System.IO.StreamWriter]::new($Jsonl,$false,[System.Text.UTF8Encoding]::new($false))
$countRows = New-Object System.Collections.Generic.List[object]

try {
    $pi = 0
    foreach ($provider in $providers) {
        $pi++
        $guidBraced = "{" + $provider.Guid + "}"
        $xpath = "*[System[Provider[@Guid='$guidBraced']]]"

        Write-Host ("[{0}/{1}] Reading {2} ..." -f $pi,$providers.Count,$provider.Name)
        $sw = [System.Diagnostics.Stopwatch]::StartNew()

        $total = 0L
        $windowCounts = @{}
        foreach ($w in $windows) { $windowCounts[$w.Name] = 0L }

        Get-WinEvent -Path $Etl -FilterXPath $xpath -Oldest -ErrorAction SilentlyContinue | ForEach-Object {
            $e = $_
            $total++
            $t = ([DateTimeOffset]$e.TimeCreated).ToUniversalTime()

            $hitWindows = @()
            foreach ($w in $windows) {
                if ($t -ge $w.Start -and $t -le $w.End) {
                    $hitWindows += $w.Name
                    $windowCounts[$w.Name]++
                }
            }

            if ($hitWindows.Count -eq 0) { return }

            $props = @()
            foreach ($p in @($e.Properties)) {
                $props += Normalize-Value $p.Value
            }

            $msg = $null
            if ($provider.IncludeMessage) {
                try { $msg = $e.FormatDescription() } catch {}
                if ($null -ne $msg -and $msg.Length -gt 8192) {
                    $msg = $msg.Substring(0,8192)
                }
            }

            $record = [ordered]@{
                status = "OBSERVED"
                time_utc = $t.ToString("o")
                windows = $hitWindows
                provider = $provider.Name
                provider_guid = $provider.Guid
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

        $sw.Stop()
        $row = [pscustomobject]@{
            provider = $provider.Name
            guid = $provider.Guid
            total_events = $total
            cold_boot = $windowCounts["COLD_BOOT"]
            t2_disable_enable = $windowCounts["T2_DISABLE_ENABLE"]
            t3_one_finger = $windowCounts["T3_ONE_FINGER"]
            t4_two_finger = $windowCounts["T4_TWO_FINGER"]
            t5_sleep_resume = $windowCounts["T5_SLEEP_RESUME"]
            t5_post_resume_finger = $windowCounts["T5_POST_RESUME_FINGER"]
            seconds = [math]::Round($sw.Elapsed.TotalSeconds,2)
        }
        $countRows.Add($row)
        Write-Host ("    {0} events total; {1:N1}s" -f $total,$sw.Elapsed.TotalSeconds)
    }
} finally {
    $writer.Dispose()
}

$countRows | Export-Csv -NoTypeInformation -Encoding utf8 $CountsCsv
$countRows | Format-Table -AutoSize | Out-String -Width 260 | Write-Host

$required = @("ACPI-Method","Kernel-Acpi","Kernel-Power","Kernel-PnP","Kernel-Process","SPB","GPIO","HIDCLASS")
$missing = @()
foreach ($name in $required) {
    $row = $countRows | Where-Object provider -eq $name | Select-Object -First 1
    if ($null -eq $row -or $row.total_events -eq 0) { $missing += $name }
}

Write-Host ""
if ($missing.Count -gt 0) {
    Write-Host ("FILTERED COVERAGE FAIL: " + ($missing -join ", "))
    exit 2
}

Write-Host "FILTERED COVERAGE PASS"
Write-Host ("JSONL: " + $Jsonl)
Write-Host ("Counts: " + $CountsCsv)
