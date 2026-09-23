param(
    [string]$OutRoot = "C:\gate2"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Xml = Join-Path $OutRoot "gate2-stream.xml"
$Markers = Join-Path $OutRoot "markers.tsv"
$Out = Join-Path $OutRoot "gate2-compact.tsv"

if (-not (Test-Path $Xml)) { throw "Missing XML: $Xml" }
if (-not (Test-Path $Markers)) { throw "Missing markers: $Markers" }

$src = @'
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Xml;

public static class Gate2CompactExtractor
{
    sealed class Window {
        public string Name;
        public DateTimeOffset Start;
        public DateTimeOffset End;
    }

    static readonly Dictionary<string,string> Providers =
        new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase) {
            {"dab01d4d-2d48-477d-b1c3-daad0ce6f06b","ACPI-Method"},
            {"c514638f-7723-485b-bcfc-96565d735d4a","Kernel-Acpi"},
            {"331c3b3a-2005-44c2-ac5e-77220c37d6b4","Kernel-Power"},
            {"9c205a39-1250-487d-abd7-e831c6290539","Kernel-PnP"},
            {"72cd9ff7-4af8-4b89-aede-5f26fda13567","SPB"},
            {"55ab77f6-fa04-43ef-af45-688fbf500482","GPIO"},
            {"6465da78-e7a0-4f39-b084-8f53c7c30dc6","HIDCLASS"},
            {"2fea7205-b0b1-41ca-8609-5a1d16f3132f","HidMini"},
            {"3fa102e9-1a62-5490-7af8-6088c2f9e6be","TouchAndPen"}
        };

    static string CleanGuid(string s) {
        if (String.IsNullOrEmpty(s)) return "";
        return s.Trim().Trim('{','}').ToLowerInvariant();
    }

    static string Esc(string s) {
        if (s == null) return "";
        return s.Replace("\\","\\\\").Replace("\t","\\t").Replace("\r","\\r").Replace("\n","\\n");
    }

    static DateTimeOffset ParseTime(string s) {
        return DateTimeOffset.Parse(s, CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
    }

    static Dictionary<string,DateTimeOffset> ReadMarkers(string path) {
        var d = new Dictionary<string,DateTimeOffset>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in File.ReadLines(path)) {
            if (String.IsNullOrWhiteSpace(line)) continue;
            var parts = line.Trim().Split((char[])null, 3, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2) continue;
            DateTimeOffset t;
            if (DateTimeOffset.TryParse(parts[0], CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out t))
                d[parts[1]] = t.ToUniversalTime();
        }
        return d;
    }

    static List<Window> BuildWindows(Dictionary<string,DateTimeOffset> m, DateTimeOffset firstEvent) {
        DateTimeOffset v;
        Func<string,DateTimeOffset> M = n => {
            if (!m.TryGetValue(n,out v)) throw new Exception("Missing marker: " + n);
            return v;
        };

        // Keep cold boot deliberately tight. We already have the first ~5 s partial
        // decode; 12 s covers reset, descriptor, and immediate post-RDESC setup
        // without retaining the entire boot-to-login interval.
        return new List<Window> {
            new Window { Name="COLD_BOOT_12S", Start=firstEvent, End=firstEvent.AddSeconds(12) },
            new Window { Name="T2_DISABLE_ENABLE", Start=M("T2_DISABLE_BEGIN").AddSeconds(-2), End=M("T3_ONE_FINGER_BEGIN").AddSeconds(-0.1) },
            new Window { Name="T3_ONE_FINGER", Start=M("T3_ONE_FINGER_BEGIN").AddSeconds(-1), End=M("T3_ONE_FINGER_END").AddSeconds(1) },
            new Window { Name="T4_TWO_FINGER", Start=M("T4_TWO_FINGER_BEGIN").AddSeconds(-1), End=M("T4_TWO_FINGER_END").AddSeconds(1) },
            new Window { Name="T5_SLEEP_RESUME", Start=M("T5_SLEEP_BEGIN").AddSeconds(-2), End=M("T5_RESUME").AddSeconds(3) },
            new Window { Name="T5_POST_RESUME_FINGER", Start=M("T5_POST_RESUME_ONE_FINGER_BEGIN").AddSeconds(-1), End=M("T5_POST_RESUME_ONE_FINGER_END").AddSeconds(1) }
        };
    }

    public static void Run(string xmlPath, string markersPath, string outPath) {
        var markers = ReadMarkers(markersPath);
        var settings = new XmlReaderSettings {
            IgnoreWhitespace = true,
            DtdProcessing = DtdProcessing.Prohibit,
            CheckCharacters = false
        };

        DateTimeOffset? firstEvent = null;
        List<Window> windows = null;
        long parsed = 0, kept = 0;
        var sw = System.Diagnostics.Stopwatch.StartNew();
        long lastReport = 0;

        using (var input = XmlReader.Create(xmlPath, settings))
        using (var output = new StreamWriter(outPath, false, new UTF8Encoding(false))) {
            output.WriteLine("window\ttime_utc\tprovider\tprovider_guid\tevent_id\tprocess_id\tthread_id\teventdata_xml\tuserdata_xml");

            while (input.Read()) {
                if (input.NodeType != XmlNodeType.Element || input.LocalName != "Event") continue;

                using (var sub = input.ReadSubtree()) {
                    string providerGuid = "", eventId = "", pid = "", tid = "";
                    string eventDataXml = "", userDataXml = "";
                    DateTimeOffset? time = null;

                    while (sub.Read()) {
                        if (sub.NodeType != XmlNodeType.Element) continue;

                        if (sub.LocalName == "Provider") {
                            providerGuid = CleanGuid(sub.GetAttribute("Guid"));
                        } else if (sub.LocalName == "TimeCreated") {
                            var st = sub.GetAttribute("SystemTime");
                            if (!String.IsNullOrEmpty(st)) {
                                DateTimeOffset t;
                                if (DateTimeOffset.TryParse(st, CultureInfo.InvariantCulture,
                                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out t))
                                    time = t.ToUniversalTime();
                            }
                        } else if (sub.LocalName == "EventID") {
                            eventId = sub.ReadElementContentAsString();
                        } else if (sub.LocalName == "Execution") {
                            pid = sub.GetAttribute("ProcessID") ?? "";
                            tid = sub.GetAttribute("ThreadID") ?? "";
                        } else if (sub.LocalName == "EventData") {
                            eventDataXml = sub.ReadOuterXml();
                        } else if (sub.LocalName == "UserData") {
                            userDataXml = sub.ReadOuterXml();
                        }
                    }

                    parsed++;
                    if (!time.HasValue) continue;

                    if (!firstEvent.HasValue) {
                        firstEvent = time.Value;
                        windows = BuildWindows(markers, firstEvent.Value);
                    }

                    string providerName;
                    if (!Providers.TryGetValue(providerGuid, out providerName)) continue;

                    foreach (var w in windows) {
                        if (time.Value < w.Start || time.Value > w.End) continue;
                        output.WriteLine(
                            Esc(w.Name) + "\t" +
                            time.Value.ToString("o") + "\t" +
                            Esc(providerName) + "\t" +
                            providerGuid + "\t" +
                            Esc(eventId) + "\t" +
                            Esc(pid) + "\t" +
                            Esc(tid) + "\t" +
                            Esc(eventDataXml) + "\t" +
                            Esc(userDataXml)
                        );
                        kept++;
                    }
                }

                if (sw.ElapsedMilliseconds - lastReport >= 5000) {
                    Console.WriteLine("parsed {0:N0}; kept {1:N0}; {2:N1} MB/s",
                        parsed, kept,
                        new FileInfo(xmlPath).Length / 1048576.0 / Math.Max(1.0, sw.Elapsed.TotalSeconds));
                    lastReport = sw.ElapsedMilliseconds;
                }
            }
        }

        Console.WriteLine("COMPACT EXTRACT COMPLETE");
        Console.WriteLine("Parsed events: {0:N0}", parsed);
        Console.WriteLine("Kept rows: {0:N0}", kept);
        Console.WriteLine("Output: " + outPath);
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ReferencedAssemblies @(
    "System.dll",
    "System.Core.dll",
    "System.Xml.dll"
)
[Gate2CompactExtractor]::Run($Xml,$Markers,$Out)

Get-Item $Out | Select-Object FullName,Length,LastWriteTime
