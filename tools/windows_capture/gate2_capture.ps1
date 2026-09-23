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

    $savedEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & wpr.exe -marker ("SL4A_GATE2::{0}::{1}" -f $Name,$Note) 2>&1 |
            Add-Content -Path (Join-Path $OutRoot "wpr-marker.log")
        $markerExit = $LASTEXITCODE
        ("{0} {1} exit={2}" -f $stamp,$Name,$markerExit) |
            Add-Content -Path (Join-Path $OutRoot "wpr-marker-status.log")
    } finally {
        $ErrorActionPreference = $savedEap
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

        $smokePass = "C:\gate2-smoke\SMOKE-PASS.txt"
        $smokePresence = "C:\gate2-smoke\provider-presence.txt"
        if (-not (Test-Path $smokePass) -or ((Get-Content -Raw $smokePass).Trim() -ne "PASS")) {
            throw "Gate 2 provider smoke has not passed. Run validate_gate2_providers.ps1 first."
        }
        if (-not (Test-Path $smokePresence)) {
            throw "Gate 2 provider smoke evidence missing: $smokePresence"
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

        $smokePass = "C:\gate2-smoke\SMOKE-PASS.txt"
        if (-not (Test-Path $smokePass) -or ((Get-Content -Raw $smokePass).Trim() -ne "PASS")) {
            throw "Gate 2 provider smoke has not passed. Refusing to arm another cold capture."
        }

        Run-Exe wpr.exe @("-profiles",$Profile) (Join-Path $OutRoot "wpr-profiles-arm.txt")

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

        # Best-effort stale boot-trace cleanup. WPR returns an error when
        # there is no boot autologger/recording to cancel; that is harmless
        # here and must not abort Arm.
        $savedEap = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & wpr.exe -boottrace -cancelboot 2>&1 |
                Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-cancelboot-before-arm.txt")
            $cancelBootExit = $LASTEXITCODE
            "exit_code=$cancelBootExit" |
                Add-Content (Join-Path $OutRoot "wpr-cancelboot-before-arm.txt")
        } finally {
            $ErrorActionPreference = $savedEap
        }

        Get-ChildItem -Path (Join-Path $OutRoot "wpr-temp") -File -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue

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
        $bootStatus = (& wpr.exe -status profiles collectors -details 2>&1 | Out-String -Width 400)
        $bootStatus | Set-Content -Encoding utf8 (Join-Path $OutRoot "wpr-status-after-boot.txt")

        $bootSession = "WPR_initiated_WprApp_boottr_TouchInitCollector"
        $etsStatus = (& logman.exe query -ets 2>&1 | Out-String -Width 400)
        $etsStatus | Set-Content -Encoding utf8 (Join-Path $OutRoot "logman-ets-after-boot.txt")

        if ($etsStatus -notmatch [regex]::Escape($bootSession)) {
            ("Boot autologger is not present in active ETW sessions." + [Environment]::NewLine + [Environment]::NewLine +
             "Expected session: " + $bootSession + [Environment]::NewLine + [Environment]::NewLine + $etsStatus) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "BOOTTRACE-NOT-ACTIVE.txt")
            throw "Gate 2 rejected: TouchInit boot autologger is not active in ETW."
        }

        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $OutRoot "BOOTTRACE-NOT-ACTIVE.txt")
        Mark-Step "T0_BOOTTRACE_ACTIVE" "logman confirms TouchInitCollector active; early-boot events precede this marker"

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

        # Do not expand the full ETL to XML here. Rich Gate 2 traces can
        # produce multi-gigabyte XML and PowerShell cannot safely load that
        # artifact with Get-Content -Raw. Structural validation is marker-
        # based; provider/event coverage is performed by the bounded-memory
        # decode_gate2_stream_xml.ps1 decoder against the saved ETL.
        $markerPath = Join-Path $OutRoot "markers.tsv"
        $markerText = if (Test-Path $markerPath) { Get-Content -Raw $markerPath } else { "" }

        $markerRows = @()
        if (Test-Path $markerPath) {
            foreach ($line in Get-Content $markerPath) {
                if ($line -match '^\s*(\S+)\s+(\S+)(?:\s+(.*))?$') {
                    try {
                        $markerRows += [pscustomobject]@{
                            time = [DateTimeOffset]::Parse($Matches[1]).ToUniversalTime()
                            step = $Matches[2]
                        }
                    } catch {}
                }
            }
        }

        $t0 = $markerRows | Where-Object step -eq "T0_PRE_BOOT" | Select-Object -First 1
        $t6 = $markerRows | Where-Object step -eq "T6_STOP" | Select-Object -Last 1
        if ($null -eq $t0 -or $null -eq $t6) {
            "Gate 2 structural postcheck failed: T0_PRE_BOOT or T6_STOP timestamp missing." |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
            throw "Gate 2 rejected: lifecycle boundary timestamps are missing."
        }

        $elapsedSeconds = ($t6.time - $t0.time).TotalSeconds
        if ($elapsedSeconds -lt 60) {
            ("Gate 2 structural postcheck failed. Marker span was {0:N1}s; expected >=60s." -f $elapsedSeconds) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
            throw "Gate 2 rejected: marker timeline does not span the full lifecycle."
        }

        ("Marker lifecycle span seconds={0:N3}" -f $elapsedSeconds) |
            Set-Content -Encoding ascii (Join-Path $OutRoot "gate2-marker-span.txt")

        $requiredLocalMarkers = @(
            "T0_PRE_BOOT",
            "T0_BOOTTRACE_ACTIVE",
            "T2_DISABLE_BEGIN",
            "T2_ENABLE_BEGIN",
            "T3_ONE_FINGER_BEGIN",
            "T4_TWO_FINGER_BEGIN",
            "T5_SLEEP_BEGIN",
            "T5_RESUME",
            "T5_POST_RESUME_ONE_FINGER_BEGIN",
            "T6_STOP"
        )
        $missingLocalMarkers = @($requiredLocalMarkers | Where-Object { $markerText -notmatch [regex]::Escape($_) })
        if ($missingLocalMarkers.Count -gt 0) {
            ("Gate 2 structural postcheck failed: required local phase markers missing:" + [Environment]::NewLine +
             ($missingLocalMarkers -join [Environment]::NewLine)) |
                Set-Content -Encoding utf8 (Join-Path $OutRoot "POSTCHECK-FAIL.txt")
            throw "Gate 2 rejected: lifecycle phase markers are incomplete. See POSTCHECK-FAIL.txt"
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
