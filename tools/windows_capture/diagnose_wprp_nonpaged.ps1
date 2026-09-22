param(
    [string]$OutRoot = "C:\gate2-wprp-diag"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile = Join-Path $ScriptDir "touch_boot.wprp"

if (-not (Test-Path $Profile)) {
    throw "Missing profile: $Profile"
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
Get-ChildItem -Path $OutRoot -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

function Save-XmlVariant {
    param(
        [xml]$Xml,
        [string]$Path
    )
    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Indent = $true
    $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $writer = [System.Xml.XmlWriter]::Create($Path, $settings)
    try {
        $Xml.Save($writer)
    } finally {
        $writer.Dispose()
    }
}

function Test-Wprp {
    param(
        [string]$Name,
        [string]$Path
    )

    $log = Join-Path $OutRoot ("{0}.log" -f $Name)
    $savedEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = (& wpr.exe -profiles $Path 2>&1 | Out-String -Width 500)
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEap
    }

    $output | Set-Content -Encoding utf8 $log

    [pscustomobject]@{
        test = $Name
        exit_code = $code
        pass = ($code -eq 0)
        path = $Path
    }
}

[xml]$source = Get-Content -Raw $Profile
$results = New-Object System.Collections.Generic.List[object]

# A: exact current profile
$currentPath = Join-Path $OutRoot "A-current.wprp"
Copy-Item $Profile $currentPath -Force
$results.Add((Test-Wprp "A-current" $currentPath))

# B: current topology/buffers, but remove every NonPagedMemory attribute
[xml]$b = $source.OuterXml
foreach ($node in @($b.WindowsPerformanceRecorder.Profiles.EventProvider)) {
    if ($node.HasAttribute("NonPagedMemory")) {
        $node.RemoveAttribute("NonPagedMemory")
    }
}
$bPath = Join-Path $OutRoot "B-no-nonpaged.wprp"
Save-XmlVariant $b $bPath
$results.Add((Test-Wprp "B-no-nonpaged" $bPath))

# C: B plus the exact old accepted buffer sizing
[xml]$c = $b.OuterXml
$collector = $c.WindowsPerformanceRecorder.Profiles.EventCollector
$collector.BufferSize.Value = "1024"
$collector.Buffers.Value = "640"
$cPath = Join-Path $OutRoot "C-old-buffers-no-nonpaged.wprp"
Save-XmlVariant $c $cPath
$results.Add((Test-Wprp "C-old-buffers-no-nonpaged" $cPath))

# D: test each provider individually with NonPagedMemory=true.
$providerIds = @(
    "Acpi-MethodTrace",
    "Kernel-Acpi",
    "Kernel-Power",
    "Kernel-PowerTrigger",
    "Kernel-Processor-Power",
    "Kernel-PnP",
    "Kernel-Process",
    "Surface-SerialHub",
    "Surface-SmfCore",
    "Surface-SmfClient",
    "Surface-PowerTrack",
    "Surface-HidMini",
    "Surface-HotPlug",
    "SPB-ClassExtension",
    "GPIO-ClassExtension",
    "Input-HIDCLASS"
)

foreach ($id in $providerIds) {
    [xml]$x = $b.OuterXml
    $node = @($x.WindowsPerformanceRecorder.Profiles.EventProvider) |
        Where-Object { $_.Id -eq $id } |
        Select-Object -First 1
    if ($null -eq $node) {
        throw "Provider not found in profile: $id"
    }
    $node.SetAttribute("NonPagedMemory","true")
    $safe = $id -replace '[^A-Za-z0-9_-]','_'
    $p = Join-Path $OutRoot ("D-one-{0}.wprp" -f $safe)
    Save-XmlVariant $x $p
    $results.Add((Test-Wprp ("D-one-{0}" -f $safe) $p))
}

# E: cumulative addition in profile order. This identifies the first
# combination that WPR rejects if all one-at-a-time tests pass.
[xml]$cum = $b.OuterXml
$step = 0
foreach ($id in $providerIds) {
    $step++
    $node = @($cum.WindowsPerformanceRecorder.Profiles.EventProvider) |
        Where-Object { $_.Id -eq $id } |
        Select-Object -First 1
    $node.SetAttribute("NonPagedMemory","true")
    $p = Join-Path $OutRoot ("E-cumulative-{0:D2}-{1}.wprp" -f $step,($id -replace '[^A-Za-z0-9_-]','_'))
    Save-XmlVariant $cum $p
    $results.Add((Test-Wprp ("E-cumulative-{0:D2}-{1}" -f $step,$id) $p))
}

$results |
    Format-Table -AutoSize |
    Out-String -Width 300 |
    Tee-Object -FilePath (Join-Path $OutRoot "RESULTS.txt") |
    Write-Host

$baseline = $results | Where-Object test -eq "B-no-nonpaged"
$current = $results | Where-Object test -eq "A-current"
$old = $results | Where-Object test -eq "C-old-buffers-no-nonpaged"

Write-Host ""
if (-not $baseline.pass -and $old.pass) {
    Write-Host "DIAGNOSIS: 256/256 collector sizing is rejected; old 1024/640 sizing parses."
} elseif (-not $baseline.pass -and -not $old.pass) {
    Write-Host "DIAGNOSIS: failure is not explained by NonPagedMemory or buffer sizing; inspect B/C logs."
} elseif ($baseline.pass -and -not $current.pass) {
    $badSingles = @($results | Where-Object { $_.test -like "D-one-*" -and -not $_.pass })
    $firstBadCum = $results | Where-Object { $_.test -like "E-cumulative-*" -and -not $_.pass } | Select-Object -First 1
    Write-Host "DIAGNOSIS: profile parses without NonPagedMemory; current NonPagedMemory set causes rejection."
    if ($badSingles.Count -gt 0) {
        Write-Host "Providers rejected individually:"
        $badSingles | ForEach-Object { Write-Host ("  " + $_.test) }
    }
    if ($null -ne $firstBadCum) {
        Write-Host ("First rejected cumulative variant: " + $firstBadCum.test)
    }
} elseif ($current.pass) {
    Write-Host "DIAGNOSIS: current profile now parses; previous failure was outside profile XML."
} else {
    Write-Host "DIAGNOSIS: see RESULTS.txt and individual logs."
}

Write-Host ""
Write-Host ("Saved diagnostics to " + $OutRoot)
