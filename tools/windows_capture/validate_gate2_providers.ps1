param(
    [string]$OutRoot = "C:\gate2-smoke"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstanceId = "ACPI\MSHW0231\A"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile = Join-Path $ScriptDir "touch_boot.wprp"
$Etl = Join-Path $OutRoot "provider-smoke.etl"
$Xml = Join-Path $OutRoot "provider-smoke.xml"
$Summary = Join-Path $OutRoot "provider-smoke-summary.txt"

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = [Security.Principal.WindowsPrincipal]::new($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell window."
    }
}

function Run-Native([string]$File,[string[]]$Args,[string]$Log) {
    & $File @Args 2>&1 | Tee-Object -FilePath $Log
    if ($LASTEXITCODE -ne 0) {
        throw "$File exited with code $LASTEXITCODE"
    }
}

Assert-Admin
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
Get-ChildItem -Path $OutRoot -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $Profile)) {
    throw "Missing WPR profile: $Profile"
}

# Validate the custom profile before starting anything. If WPR rejects the
# XML/profile schema, fail here with the exact diagnostic rather than after
# device state has been changed.
Run-Native wpr.exe @("-profiles",$Profile) (Join-Path $OutRoot "wpr-profiles.txt")

# Do not disturb the boot-autologger registry configuration. This smoke test
# uses a normal WPR session only.
$savedEap = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & wpr.exe -cancel 2>&1 | Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-cancel-before-smoke.txt")
} finally {
    $ErrorActionPreference = $savedEap
}

Run-Native wpr.exe @("-start",("$Profile!TouchInit.Verbose"),"-filemode") (Join-Path $OutRoot "wpr-start.txt")
Start-Sleep -Seconds 2

& wpr.exe -status profiles collectors -details 2>&1 |
    Out-File -Encoding utf8 (Join-Path $OutRoot "wpr-status-running.txt")

# Force a process event after tracing starts.
& cmd.exe /c exit

Run-Native pnputil.exe @("/disable-device",$InstanceId,"/force") (Join-Path $OutRoot "pnputil-disable.txt")
Start-Sleep -Seconds 3
Run-Native pnputil.exe @("/enable-device",$InstanceId) (Join-Path $OutRoot "pnputil-enable.txt")
Start-Sleep -Seconds 3

Read-Host "Perform ONE finger down -> drag -> up for a few seconds, then press Enter"

Run-Native wpr.exe @("-stop",$Etl,"SL4A Gate 2 provider smoke") (Join-Path $OutRoot "wpr-stop.txt")

Run-Native tracerpt.exe @(
    $Etl,
    "-o",$Xml,
    "-of","XML",
    "-lr",
    "-summary",$Summary,
    "-y"
) (Join-Path $OutRoot "tracerpt.log")

$haystack = ((Get-Content -Raw $Xml) + [Environment]::NewLine + (Get-Content -Raw $Summary)).ToLowerInvariant()

$providers = [ordered]@{
    "ACPI-Method"   = "dab01d4d-2d48-477d-b1c3-daad0ce6f06b"
    "Kernel-Acpi"   = "c514638f-7723-485b-bcfc-96565d735d4a"
    "Kernel-Power"  = "331c3b3a-2005-44c2-ac5e-77220c37d6b4"
    "Kernel-PnP"    = "9c205a39-1250-487d-abd7-e831c6290539"
    "Kernel-Process"= "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716"
    "SPB"           = "72cd9ff7-4af8-4b89-aede-5f26fda13567"
    "GPIO"          = "55ab77f6-fa04-43ef-af45-688fbf500482"
    "HIDCLASS"      = "6465da78-e7a0-4f39-b084-8f53c7c30dc6"
    "HidMini"       = "2fea7205-b0b1-41ca-8609-5a1d16f3132f"
    "TouchAndPen"   = "3fa102e9-1a62-5490-7af8-6088c2f9e6be"
}

$rows = foreach ($kv in $providers.GetEnumerator()) {
    [pscustomobject]@{
        provider = $kv.Key
        guid = $kv.Value
        observed = $haystack.Contains($kv.Value)
    }
}
$rows | Format-Table -AutoSize | Out-String | Tee-Object -FilePath (Join-Path $OutRoot "provider-presence.txt") | Write-Host

$present = @($rows | Where-Object observed | ForEach-Object provider)

# The smoke is intentionally evidence-driven. Device disable/enable must
# produce Kernel-PnP, and a real finger interaction must produce at least one
# transport/input-side provider. ACPI may legitimately be absent if Windows
# performs no ACPI method in this runtime cycle, so it is reported but is not
# the sole pass condition here.
$fail = @()
if ($present -notcontains "Kernel-PnP") {
    $fail += "Kernel-PnP absent after explicit disable/enable"
}
if (($present -notcontains "SPB") -and ($present -notcontains "HIDCLASS") -and ($present -notcontains "HidMini")) {
    $fail += "No SPB/HIDCLASS/HidMini events observed during real touch"
}
if ($present -notcontains "Kernel-Process") {
    $fail += "Kernel-Process absent despite creating cmd.exe after trace start"
}

$hash = (Get-FileHash -Algorithm SHA256 $Etl).Hash.ToLowerInvariant()
"ETL_SHA256=$hash" | Set-Content -Encoding ascii (Join-Path $OutRoot "provider-smoke-sha256.txt")

if ($fail.Count -gt 0) {
    $fail | Set-Content -Encoding utf8 (Join-Path $OutRoot "SMOKE-FAIL.txt")
    throw "Gate 2 provider smoke FAILED. See $OutRoot\SMOKE-FAIL.txt and provider-presence.txt"
}

"PASS" | Set-Content -Encoding ascii (Join-Path $OutRoot "SMOKE-PASS.txt")
Write-Host ""
Write-Host "Gate 2 provider smoke PASSED."
Write-Host "Do not run another cold capture until this PASS exists."
Write-Host "Evidence: $OutRoot"
