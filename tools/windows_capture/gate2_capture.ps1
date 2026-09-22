param(
    [ValidateSet("Preflight","Arm","Resume")]
    [string]$Phase = "Preflight",

    [string]$OutRoot = "C:\gate2",

    [switch]$PowerOff
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstanceId = "ACPI\MSHW0231\A"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile    = Join-Path $ScriptDir "touch_boot.wprp"
$DumpHid    = Join-Path $ScriptDir "dump_hid_report_descriptor.ps1"

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = [Security.Principal.WindowsPrincipal]::new($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell window."
    }
}

function Ensure-Dir([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Run-Exe {
    param(
        [Parameter(Mandatory=$true)][string]$File,
        [Parameter(Mandatory=$true)][string[]]$Args,
        [string]$Stdout
    )

    if ($Stdout) {
        & $File @Args 2>&1 | Tee-Object -FilePath $Stdout
    } else {
        & $File @Args
    }

    if ($LASTEXITCODE -ne 0) {
        throw "${File} exited with code ${LASTEXITCODE}: $($Args -join ' ')"
    }
}

function Mark-Step {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [string]$Note = "",
        [switch]$LocalOnly
    )

    $stamp = [DateTimeOffset]::UtcNow.ToString("o")
    $safe  = $Name -replace '[^A-Za-z0-9_.-]','_'
    $line  = "$stamp`t$Name`t$Note"

    Add-Content -Path (Join-Path $OutRoot "markers.tsv") -Value $line
    Set-Content -Path (Join-Path $OutRoot ("marker_{0}.txt" -f $safe)) -Value $line

    if ($LocalOnly) {
        return
    }

    & wpr.exe -marker ("SL4A_GATE2::{0}::{1}" -f $Name,$Note) 2>&1 |
        Add-Content -Path (Join-Path $OutRoot "wpr-marker.log")

    if ($LASTEXITCODE -ne 0) {
        throw "WPR marker failed at $Name. The active Gate 2 session is not healthy; reject this capture."
    }
}

function Save-PnpEvidence {
    $pnp = Join-Path $OutRoot "pnputil-MSHW0231.txt"
    & pnputil.exe /enum-devices /instanceid $InstanceId /deviceids /relations /services /stack /drivers /interfaces /properties /resources 2>&1 |
        Out-File -Encoding utf8 $pnp

    Get-PnpDevice -PresentOnly |
        Where-Object { $_.InstanceId -match 'MSHW0231|AMDI0060' } |
        Format-List * |
        Out-File -Encoding utf8 (Join-Path $OutRoot "pnp-touch-devices.txt")

    $targets = Get-PnpDevice -PresentOnly |
        Where-Object { $_.InstanceId -match 'MSHW0231|AMDI0060' }

    foreach ($d in $targets) {
        "===== $($d.InstanceId) =====" |
            Add-Content -Path (Join-Path $OutRoot "pnp-device-properties.txt")
        Get-PnpDeviceProperty -InstanceId $d.InstanceId -ErrorAction Continue |
            Format-List * |
            Out-String |
            Add-Content -Path (Join-Path $OutRoot "pnp-device-properties.txt")
    }

    & powercfg.exe /a 2>&1 |
        Out-File -Encoding utf8 (Join-Path $OutRoot "powercfg-a.txt")

    & reg.exe query "HKLM\SYSTEM\CurrentControlSet\Enum\ACPI\MSHW0231" /s 2>&1 |
        Out-File -Encoding utf8 (Join-Path $OutRoot "reg-MSHW0231.txt")
}

function Save-SetupApiSlice {
    $src = Join-Path $env:windir "INF\setupapi.dev.log"
    $dst = Join-Path $OutRoot "setupapi-MSHW0231-slice.txt"

    if (-not (Test-Path $src)) {
        "setupapi.dev.log not found at $src" | Set-Content $dst
        return
    }

    Select-String -Path $src `
        -Pattern 'MSHW0231|PNP0C51|hidspi|SurfaceDigitizerHidSpi|SurfaceTouchPenProcessor|TouchPenProcessor0C19|oem31\.inf' `
        -Context 10,30 |
        Out-String -Width 400 |
        Set-Content -Encoding utf8 $dst
}

function Save-Descriptor {
    $log = Join-Path $OutRoot "report-descriptor-dump.log"

    if (-not (Test-Path $DumpHid)) {
        "descriptor helper missing: $DumpHid" | Set-Content $log
        return
    }

    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass `
            -File $DumpHid `
            -OutDir $OutRoot 2>&1 |
            Tee-Object -FilePath $log

        if ($LASTEXITCODE -ne 0) {
            "descriptor helper returned $LASTEXITCODE; same-boot RDESC must be recovered from ETL before Gate 2 can pass." |
                Add-Content $log
        }
    } catch {
        "descriptor helper failed: $($_.Exception.Message)" | Add-Content $log
    }
}


function Invoke-Gate2Sleep {
    Add-Type -AssemblyName System.Windows.Forms

    Write-Host ""
    Write-Host "Windows will enter Sleep now."
    Write-Host "After the screen turns off, WAIT AT LEAST 15 SECONDS before waking it."
    Write-Host "Wake with the keyboard or power button. The script will continue automatically after resume."
    Write-Host ""

    $ok = [System.Windows.Forms.Application]::SetSuspendState(
        [System.Windows.Forms.PowerState]::Suspend,
        $false,
        $false
    )

    if (-not $ok) {
        throw "Windows rejected the suspend request. Reject this capture and rerun Gate 2."
    }

    # Execution resumes here after Windows returns from the suspend transition.
    Start-Sleep -Seconds 3
}

function Write-Manifest {
    $files = Get-ChildItem -File $OutRoot | Sort-Object Name
    $rows = foreach ($f in $files) {
        $hash = $null
        try { $hash = (Get-FileHash -Algorithm SHA256 $f.FullName).Hash.ToLowerInvariant() } catch {}
        [pscustomobject]@{
            name   = $f.Name
            bytes  = $f.Length
            sha256 = $hash
        }
    }

    [pscustomobject]@{
        created_utc = [DateTimeOffset]::UtcNow.ToString("o")
        instance_id = $InstanceId
        computer    = $env:COMPUTERNAME
        files       = $rows
    } |
        ConvertTo-Json -Depth 5 |
        Set-Content -Encoding utf8 (Join-Path $OutRoot "capture-manifest.json")
}

Assert-Admin
Ensure-Dir $OutRoot
Ensure-Dir (Join-Path $OutRoot "wpr-temp")

switch ($Phase) {
    "Preflight" {
        if (-not (Test-Path $Profile)) {
            throw "Missing WPR profile: $Profile"
        }

        Run-Exe wpr.exe @("-profiles",$Profile) (Join-Path $OutRoot "wpr-profiles.txt")
        & wpr.exe -help boottrace 2>&1 |
            Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-boottrace-help.txt")

        $providers = & logman.exe query providers 2>&1 | Out-String -Width 400
        $providers | Set-Content -Encoding utf8 (Join-Path $OutRoot "providers-current.txt")

        $required = [ordered]@{
            "ACPI Driver Trace Provider"               = "DAB01D4D-2D48-477D-B1C3-DAAD0CE6F06B"
            "Microsoft-Windows-Kernel-Acpi"            = "C514638F-7723-485B-BCFC-96565D735D4A"
            "Microsoft-Windows-Kernel-PnP"             = "9C205A39-1250-487D-ABD7-E831C6290539"
            "Microsoft-Windows-Kernel-Power"           = "331C3B3A-2005-44C2-AC5E-77220C37D6B4"
            "Microsoft-Windows-SPB-ClassExtension"     = "72CD9FF7-4AF8-4B89-AEDE-5F26FDA13567"
            "Microsoft-Windows-GPIO-ClassExtension"    = "55AB77F6-FA04-43EF-AF45-688FBF500482"
            "Microsoft-Windows-Input-HIDCLASS"         = "6465DA78-E7A0-4F39-B084-8F53C7C30DC6"
            "Microsoft-Windows-Kernel-Process"         = "22FB2CD6-0E7B-422B-A0C7-2FAD1FD0E716"
            "Microsoft-Surface-SurfaceHidMiniDriver"   = "2FEA7205-B0B1-41CA-8609-5A1D16F3132F"
        }

        $missing = @()
        foreach ($kv in $required.GetEnumerator()) {
            if ($providers -notmatch [regex]::Escape($kv.Value)) {
                $missing += "$($kv.Key) {$($kv.Value)}"
            }
        }

        # This production Surface TouchAndPen provider was observed in prior
        # capture work and is enabled by GUID in touch_boot.wprp, but it is
        # not guaranteed to appear in 'logman query providers' on this build.
        # Keep it best-effort: its absence must not block the core ACPI/SPB/
        # GPIO/HIDCLASS lifecycle capture.
        $touchAndPenGuid = "3FA102E9-1A62-5490-7AF8-6088C2F9E6BE"
        if ($providers -match [regex]::Escape($touchAndPenGuid)) {
            "PRESENT Microsoft-Surface-TouchAndPen-Prod {$touchAndPenGuid}" |
                Set-Content (Join-Path $OutRoot "optional-providers.txt")
        } else {
            "NOT LISTED by logman; still enabled by GUID in touch_boot.wprp: Microsoft-Surface-TouchAndPen-Prod {$touchAndPenGuid}" |
                Set-Content (Join-Path $OutRoot "optional-providers.txt")
        }

        if ($missing.Count -gt 0) {
            $missing | Set-Content (Join-Path $OutRoot "PRECHECK-FAIL.txt")
            throw "Required providers missing. Capture rejected before start. See PRECHECK-FAIL.txt"
        }

        Save-PnpEvidence
        & wpr.exe -status 2>&1 |
            Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-status-preflight.txt")

        @"
Gate 2 preflight passed.

Next:
  powershell -ExecutionPolicy Bypass -File "$($MyInvocation.MyCommand.Path)" -Phase Arm -PowerOff

That configures a file-mode WPR boot autologger and powers the machine fully off.
The recorder starts automatically on the next cold power-on.
Power the Surface back on, sign in, then run the same script with -Phase Resume as Administrator.
"@ | Set-Content -Encoding utf8 (Join-Path $OutRoot "NEXT.txt")

        Write-Host "Gate 2 preflight PASSED."
        Write-Host "Next command:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" -Phase Arm -PowerOff"
    }

    "Arm" {
        if (-not (Test-Path $Profile)) {
            throw "Missing WPR profile: $Profile"
        }

        & wpr.exe -status 2>&1 |
            Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-status-before-arm.txt")

        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "markers.tsv")
        Get-ChildItem -Path $OutRoot -Filter "marker_*.txt" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "gate2.etl")
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "gate2-postcheck-summary.txt")
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "gate2-postcheck.xml")
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "decode")
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "BOOTTRACE-NOT-ACTIVE.txt")

        & wpr.exe -boottrace -cancelboot 2>&1 |
            Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-cancelboot-before-arm.txt")

        Run-Exe wpr.exe @(
            "-boottrace",
            "-addboot",("$Profile!TouchInit.Verbose"),
            "-filemode",
            "-recordtempto",(Join-Path $OutRoot "wpr-temp")
        ) (Join-Path $OutRoot "wpr-addboot.txt")

        Mark-Step "T0_PRE_BOOT" "boot autologger configured; next transition is full shutdown/power-on" -LocalOnly

        @"
WPR boot autologger is configured.

After the machine boots:
  1. sign in;
  2. open Administrator PowerShell;
  3. run:
     powershell -ExecutionPolicy Bypass -File "$($MyInvocation.MyCommand.Path)" -Phase Resume
"@ | Set-Content -Encoding utf8 (Join-Path $OutRoot "RESUME.txt")

        if ($PowerOff) {
            Write-Host "Powering off with shutdown.exe /s (not /hybrid). Power the Surface back on manually."
            Start-Sleep -Seconds 2
            & shutdown.exe /s /t 0 /f
        } else {
            Write-Host "Boot autologger configured. Perform a full shutdown/power-on now, then run -Phase Resume."
        }
    }

    "Resume" {
        $bootStatus = (& wpr.exe -status 2>&1 | Out-String -Width 400)
        $bootStatus | Set-Content -Encoding utf8 (Join-Path $OutRoot "wpr-status-after-boot.txt")

        if ($bootStatus -match "not recording|stopped and waiting to be merged" -or
            $bootStatus -notmatch "Time since start") {
            ("Boot autologger is not actively recording after cold boot." + [Environment]::NewLine + [Environment]::NewLine + $bootStatus) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "BOOTTRACE-NOT-ACTIVE.txt")
            throw "Gate 2 rejected: boot autologger is not actively recording after cold boot."
        }

        Mark-Step "T0_BOOTTRACE_ACTIVE" "first post-login marker; early-boot events precede this marker"

        Mark-Step "T1_DESKTOP_IDLE_BEGIN" "10-second idle"
        Start-Sleep -Seconds 10
        Mark-Step "T1_DESKTOP_IDLE_END"

        Mark-Step "T2_DISABLE_BEGIN" $InstanceId
        Run-Exe pnputil.exe @("/disable-device",$InstanceId,"/force") (Join-Path $OutRoot "pnputil-disable.txt")
        Start-Sleep -Seconds 5
        Mark-Step "T2_ENABLE_BEGIN" $InstanceId
        Run-Exe pnputil.exe @("/enable-device",$InstanceId) (Join-Path $OutRoot "pnputil-enable.txt")
        Start-Sleep -Seconds 5
        Mark-Step "T2_ENABLE_SETTLED"

        Mark-Step "T3_ONE_FINGER_BEGIN" "drag then lift"
        Read-Host "Perform ONE finger down -> drag -> up. Then press Enter"
        Mark-Step "T3_ONE_FINGER_END"

        Mark-Step "T4_TWO_FINGER_BEGIN" "pinch/spread then lift"
        Read-Host "Perform TWO-finger pinch/spread, then lift both fingers. Then press Enter"
        Mark-Step "T4_TWO_FINGER_END"

        Read-Host "T5: Press Enter and the script will put Windows to Sleep. After the screen turns off, wait >=15 seconds before waking it"
        Mark-Step "T5_SLEEP_BEGIN" "script-initiated suspend; wait >=15 seconds before wake"
        Invoke-Gate2Sleep
        Mark-Step "T5_RESUME" "script resumed after Windows suspend transition"

        Mark-Step "T5_POST_RESUME_ONE_FINGER_BEGIN"
        Read-Host "Perform ONE finger down -> drag -> up after resume. Then press Enter"
        Mark-Step "T5_POST_RESUME_ONE_FINGER_END"

        Mark-Step "T6_EVIDENCE_EXPORT_BEGIN"
        Save-PnpEvidence
        Save-SetupApiSlice
        Save-Descriptor
        Mark-Step "T6_EVIDENCE_EXPORT_END"

        Mark-Step "T6_STOP"
        $etlPath = Join-Path $OutRoot "gate2.etl"
        Run-Exe wpr.exe @(
            "-boottrace",
            "-stopboot",$etlPath,
            "SL4A Gate 2 golden lifecycle"
        ) (Join-Path $OutRoot "wpr-stopboot.txt")

        & wpr.exe -status 2>&1 |
            Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-status-after-stop.txt")

        $postSummary = Join-Path $OutRoot "gate2-postcheck-summary.txt"
        $postXml = Join-Path $OutRoot "gate2-postcheck.xml"
        Run-Exe tracerpt.exe @(
            $etlPath,
            "-o",$postXml,
            "-of","XML",
            "-lr",
            "-summary",$postSummary,
            "-y"
        ) (Join-Path $OutRoot "tracerpt-postcheck.log")

        $summaryText = Get-Content -Raw $postSummary
        $elapsedSeconds = $null
        if ($summaryText -match "Elapsed Time\s+(\d+)\s+sec") {
            $elapsedSeconds = [int]$Matches[1]
        }
        if ($null -eq $elapsedSeconds -or $elapsedSeconds -lt 60) {
            ("Gate 2 structural postcheck failed. Expected >=60 seconds spanning boot through T6." + [Environment]::NewLine + [Environment]::NewLine + $summaryText) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
            throw "Gate 2 rejected: ETL does not span the full lifecycle. See POSTCHECK-FAIL.txt"
        }

        $postXmlText = Get-Content -Raw $postXml
        $requiredTraceMarkers = @(
            "SL4A_GATE2::T0_BOOTTRACE_ACTIVE",
            "SL4A_GATE2::T2_DISABLE_BEGIN",
            "SL4A_GATE2::T2_ENABLE_BEGIN",
            "SL4A_GATE2::T5_SLEEP_BEGIN",
            "SL4A_GATE2::T5_RESUME",
            "SL4A_GATE2::T6_STOP"
        )
        $missingTraceMarkers = @($requiredTraceMarkers | Where-Object { $postXmlText -notmatch [regex]::Escape($_) })
        if ($missingTraceMarkers.Count -gt 0) {
            ("Gate 2 structural postcheck failed: required ETL markers missing:" + [Environment]::NewLine +
             ($missingTraceMarkers -join [Environment]::NewLine)) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
            throw "Gate 2 rejected: lifecycle markers are missing from the ETL. See POSTCHECK-FAIL.txt"
        }

        Write-Manifest

        @"
Capture complete.

DO NOT change the Linux driver yet.

Gate 2 remains RED until gate2.etl is decoded into:
  evidence/windows/gate2/windows-golden.jsonl
and all four questions in docs/GATE2-CAPTURE.md are answered with OBSERVED rows.
"@ | Set-Content -Encoding utf8 (Join-Path $OutRoot "DECODE-NEXT.txt")

        Write-Host "Gate 2 capture saved to $OutRoot\gate2.etl"
        Write-Host "Next action: decode and apply the binary pass/fail contract. No Linux patch yet."
    }
}
