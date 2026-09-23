param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Xml = Join-Path $OutRoot "gate2-stream.xml"
$Markers = Join-Path $OutRoot "markers.tsv"
$Out = Join-Path $OutRoot "gate2-process-map.tsv"

if (-not (Test-Path $Xml)) { throw "Missing XML: $Xml" }
if (-not (Test-Path $Markers)) { throw "Missing markers: $Markers" }

$stop = $null
foreach ($line in Get-Content $Markers) {
    if ($line -match '^\s*(\S+)\s+T3_ONE_FINGER_BEGIN\b') {
        $stop = [DateTimeOffset]::Parse($Matches[1]).ToUniversalTime()
        break
    }
}
if ($null -eq $stop) { throw "T3_ONE_FINGER_BEGIN marker not found" }

$src = @'
using System;
using System.Globalization;
using System.IO;
using System.Text;
using System.Xml;

public static class Gate2ProcessMap
{
    static string Esc(string s) {
        if (s == null) return "";
        return s.Replace("\\","\\\\").Replace("\t","\\t")
                .Replace("\r","\\r").Replace("\n","\\n");
    }

    public static void Run(string xmlPath, string outPath, DateTimeOffset stopUtc) {
        var settings = new XmlReaderSettings {
            IgnoreWhitespace = true,
            DtdProcessing = DtdProcessing.Prohibit,
            CheckCharacters = false
        };

        long parsed = 0, kept = 0;
        using (var input = XmlReader.Create(xmlPath, settings))
        using (var output = new StreamWriter(outPath, false, new UTF8Encoding(false))) {
            output.WriteLine("time_utc\tevent_id\texec_pid\texec_tid\teventdata_xml\tuserdata_xml");

            while (input.Read()) {
                if (input.NodeType != XmlNodeType.Element || input.LocalName != "Event")
                    continue;

                using (var sub = input.ReadSubtree()) {
                    string eventId = "", pid = "", tid = "";
                    string eventData = "", userData = "";
                    DateTimeOffset? time = null;

                    while (sub.Read()) {
                        if (sub.NodeType != XmlNodeType.Element) continue;
                        if (sub.LocalName == "EventID") {
                            eventId = sub.ReadElementContentAsString();
                        } else if (sub.LocalName == "Execution") {
                            pid = sub.GetAttribute("ProcessID") ?? "";
                            tid = sub.GetAttribute("ThreadID") ?? "";
                        } else if (sub.LocalName == "TimeCreated") {
                            var st = sub.GetAttribute("SystemTime");
                            DateTimeOffset t;
                            if (!String.IsNullOrEmpty(st) &&
                                DateTimeOffset.TryParse(st, CultureInfo.InvariantCulture,
                                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out t))
                                time = t.ToUniversalTime();
                        } else if (sub.LocalName == "EventData") {
                            eventData = sub.ReadOuterXml();
                        } else if (sub.LocalName == "UserData") {
                            userData = sub.ReadOuterXml();
                        }
                    }

                    parsed++;
                    if (!time.HasValue) continue;
                    if (time.Value > stopUtc) break;

                    // Kernel-Process Start/Stop are IDs 1/2 in this trace.
                    // Other providers can reuse those IDs, so preserve raw XML
                    // and let the audit classify only records that contain
                    // process metadata / target PIDs.
                    if (eventId != "1" && eventId != "2") continue;

                    output.WriteLine(
                        time.Value.ToString("o") + "\t" +
                        Esc(eventId) + "\t" + Esc(pid) + "\t" + Esc(tid) + "\t" +
                        Esc(eventData) + "\t" + Esc(userData));
                    kept++;
                }

                if ((parsed % 100000) == 0)
                    Console.WriteLine("parsed {0:N0}; kept {1:N0}", parsed, kept);
            }
        }

        Console.WriteLine("PROCESS MAP EXTRACT COMPLETE");
        Console.WriteLine("Parsed events: {0:N0}", parsed);
        Console.WriteLine("Kept candidate rows: {0:N0}", kept);
        Console.WriteLine("Output: " + outPath);
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ReferencedAssemblies @(
    "System.dll",
    "System.Core.dll",
    "System.Xml.dll"
)
[Gate2ProcessMap]::Run($Xml,$Out,$stop)

Write-Host ""
Write-Host "Target PID matches:"
Select-String -Path $Out -Pattern '(^|[^0-9])(2216|15596)([^0-9]|$)' |
    ForEach-Object { $_.Line }

Get-Item $Out | Select-Object FullName,Length,LastWriteTime
