param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Etl = Join-Path $OutRoot "gate2.etl"
$Xml = Join-Path $OutRoot "gate2-stream.xml"
$Summary = Join-Path $OutRoot "gate2-stream-summary.txt"
$Markers = Join-Path $OutRoot "markers.tsv"
$Jsonl = Join-Path $OutRoot "gate2-stream-windowed.jsonl"
$CountsCsv = Join-Path $OutRoot "gate2-stream-windowed-counts.csv"
$WindowsCsv = Join-Path $OutRoot "gate2-stream-windowed-windows.csv"
$ProviderPresence = Join-Path $OutRoot "gate2-stream-provider-presence.txt"

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

function Parse-Utc([string]$s) {
    if ([string]::IsNullOrWhiteSpace($s)) { return $null }
    try { return [DateTimeOffset]::Parse($s).ToUniversalTime() } catch { return $null }
}

function Extract-Guid([System.Xml.XmlElement]$event) {
    $provider = $event.SelectSingleNode("./*[local-name()='System']/*[local-name()='Provider']")
    if ($null -eq $provider) { return "" }
    $g = $provider.GetAttribute("Guid")
    if ([string]::IsNullOrWhiteSpace($g)) { return "" }
    return $g.Trim().Trim('{','}').ToLowerInvariant()
}

function Extract-Time([System.Xml.XmlElement]$event) {
    $node = $event.SelectSingleNode("./*[local-name()='System']/*[local-name()='TimeCreated']")
    if ($null -eq $node) { return $null }
    return Parse-Utc $node.GetAttribute("SystemTime")
}

function Get-SystemAttr([System.Xml.XmlElement]$event,[string]$name,[string]$attr) {
    $xpath = "./*[local-name()='System']/*[local-name()='" + $name + "']"
    $n = $event.SelectSingleNode($xpath)
    if ($null -eq $n) { return $null }
    if ([string]::IsNullOrWhiteSpace($attr)) { return $n.InnerText }
    return $n.GetAttribute($attr)
}

function Event-ToRecord([System.Xml.XmlElement]$event,[string]$window,[string]$providerName,[string]$guid,[DateTimeOffset]$time) {
    $data = @()
    foreach ($n in @($event.SelectNodes("./*[local-name()='EventData']/*[local-name()='Data']"))) {
        $name = $n.GetAttribute("Name")
        $data += [ordered]@{
            name = $name
            value = $n.InnerText
        }
    }

    [ordered]@{
        status = "OBSERVED"
        window = $window
        time_utc = $time.ToString("o")
        provider = $providerName
        provider_guid = $guid
        event_id = Get-SystemAttr $event "EventID" ""
        version = Get-SystemAttr $event "Version" ""
        level = Get-SystemAttr $event "Level" ""
        task = Get-SystemAttr $event "Task" ""
        opcode = Get-SystemAttr $event "Opcode" ""
        process_id = Get-SystemAttr $event "Execution" "ProcessID"
        thread_id = Get-SystemAttr $event "Execution" "ThreadID"
        event_record_id = Get-SystemAttr $event "EventRecordID" ""
        eventdata = $data
        userdata_xml = $( 
            $u = $event.SelectSingleNode("./*[local-name()='UserData']")
            if ($null -ne $u) { $u.InnerXml } else { $null }
        )
    }
}

$markerMap = @{}
foreach ($line in Get-Content $Markers) {
    if ($line -match '^\s*(\S+)\s+(\S+)(?:\s+(.*))?$') {
        $ts = Parse-Utc $Matches[1]
        if ($null -ne $ts) { $markerMap[$Matches[2]] = $ts }
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

# One native traversal only. XML may be several GB, but we never load it whole.
$needExport = (-not (Test-Path $Xml)) -or ((Get-Item $Xml).LastWriteTimeUtc -lt (Get-Item $Etl).LastWriteTimeUtc)
if ($needExport) {
    Write-Host "Native ETL -> XML export (one pass)..."
    & tracerpt.exe $Etl -o $Xml -of XML -lr -summary $Summary -y
    if ($LASTEXITCODE -ne 0) {
        throw "tracerpt export failed with code $LASTEXITCODE"
    }
} else {
    Write-Host "Using existing XML export: $Xml"
}

Write-Host "Streaming XML; RAM use stays bounded..."

$settings = [System.Xml.XmlReaderSettings]::new()
$settings.IgnoreWhitespace = $true
$settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
$reader = [System.Xml.XmlReader]::Create($Xml,$settings)

$etlStart = $null
$windows = $null
$counts = @{}
$totalProviderCounts = @{}
foreach ($p in $providers.Values) { $totalProviderCounts[$p] = 0L }

Remove-Item -Force -ErrorAction SilentlyContinue $Jsonl,$CountsCsv,$WindowsCsv,$ProviderPresence
$writer = [System.IO.StreamWriter]::new($Jsonl,$false,[System.Text.UTF8Encoding]::new($false))

$eventCount = 0L
$matchedCount = 0L
$lastProgress = [DateTime]::UtcNow

try {
    while ($reader.Read()) {
        if ($reader.NodeType -ne [System.Xml.XmlNodeType]::Element -or $reader.Name -ne "Event") { continue }

        $outer = $reader.ReadOuterXml()
        if ([string]::IsNullOrWhiteSpace($outer)) { continue }

        $doc = [System.Xml.XmlDocument]::new()
        $doc.PreserveWhitespace = $false
        $doc.LoadXml($outer)
        $event = $doc.DocumentElement
        $eventCount++

        $time = Extract-Time $event
        if ($null -eq $time) { continue }

        if ($null -eq $etlStart) {
            $etlStart = $time
            $windows = @(
                [pscustomobject]@{ Name="COLD_BOOT"; Start=$etlStart; End=$markerMap["T0_BOOTTRACE_ACTIVE"].AddSeconds(2) },
                [pscustomobject]@{ Name="T2_DISABLE_ENABLE"; Start=$markerMap["T2_DISABLE_BEGIN"].AddSeconds(-1); End=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.1) },
                [pscustomobject]@{ Name="T3_ONE_FINGER"; Start=$markerMap["T3_ONE_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T3_ONE_FINGER_END"].AddSeconds(0.5) },
                [pscustomobject]@{ Name="T4_TWO_FINGER"; Start=$markerMap["T4_TWO_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T4_TWO_FINGER_END"].AddSeconds(0.5) },
                [pscustomobject]@{ Name="T5_SLEEP_RESUME"; Start=$markerMap["T5_SLEEP_BEGIN"].AddSeconds(-1); End=$markerMap["T5_RESUME"].AddSeconds(2) },
                [pscustomobject]@{ Name="T5_POST_RESUME_FINGER"; Start=$markerMap["T5_POST_RESUME_ONE_FINGER_BEGIN"].AddSeconds(-0.5); End=$markerMap["T5_POST_RESUME_ONE_FINGER_END"].AddSeconds(0.5) }
            )
            $windows | Export-Csv -NoTypeInformation -Encoding utf8 $WindowsCsv
            foreach ($w in $windows) {
                foreach ($p in $providers.Values) {
                    $counts["$($w.Name)|$p"] = 0L
                }
            }
        }

        $guid = Extract-Guid $event
        if (-not $providers.Contains($guid)) {
            if (([DateTime]::UtcNow - $lastProgress).TotalSeconds -ge 15) {
                Write-Host ("  parsed {0:N0} events; retained {1:N0}" -f $eventCount,$matchedCount)
                $lastProgress = [DateTime]::UtcNow
            }
            continue
        }

        $providerName = $providers[$guid]
        $totalProviderCounts[$providerName]++

        foreach ($w in $windows) {
            if ($time -ge $w.Start -and $time -le $w.End) {
                $counts["$($w.Name)|$providerName"]++
                $record = Event-ToRecord $event $w.Name $providerName $guid $time
                $writer.WriteLine(($record | ConvertTo-Json -Depth 8 -Compress))
                $matchedCount++
            }
        }

        if (([DateTime]::UtcNow - $lastProgress).TotalSeconds -ge 15) {
            Write-Host ("  parsed {0:N0} events; retained {1:N0}" -f $eventCount,$matchedCount)
            $lastProgress = [DateTime]::UtcNow
        }
    }
} finally {
    $writer.Dispose()
    $reader.Dispose()
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

$presenceRows = foreach ($p in $providers.Values) {
    [pscustomobject]@{
        provider = $p
        total_events = [int64]$totalProviderCounts[$p]
        observed = ([int64]$totalProviderCounts[$p] -gt 0)
    }
}
$presenceRows | Format-Table -AutoSize | Out-String -Width 160 | Set-Content -Encoding utf8 $ProviderPresence

Write-Host ""
Write-Host "STREAMING DECODE COMPLETE"
Write-Host ("Parsed events: " + $eventCount)
Write-Host ("Retained target-window events: " + $matchedCount)
Write-Host ("JSONL: " + $Jsonl)
Write-Host ("Counts: " + $CountsCsv)
Write-Host ("Provider presence: " + $ProviderPresence)
