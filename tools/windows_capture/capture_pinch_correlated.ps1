# SL4A Windows paired pinch experiment. Captures WPR and Win32 OS pointers
# on the same local run. No reboot, driver changes, reset or wpr -cancel.
param(
  [ValidateSet('Capture','Export','Preflight','SelfTest')]
  [string]$Mode='Capture',
  [string]$RunDir='',
  [switch]$SkipCsvExport,
  [switch]$PhysicalTruthMode
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Profile=Join-Path $Here 'touch_boot.wprp'
$Pointer=Join-Path $Here 'capture_os_pointer_contacts_v2.ps1'
function Assert-Assets {
  if(-not (Test-Path -LiteralPath $Profile -PathType Leaf)){throw "Missing touch_boot.wprp in $Here"}
  if(-not (Test-Path -LiteralPath $Pointer -PathType Leaf)){throw "Missing V2 pointer file in $Here"}
  $xml=[xml](Get-Content -LiteralPath $Profile -Raw)
  $providers=@($xml.WindowsPerformanceRecorder.Profiles.EventProvider)
  $touch=@($providers | Where-Object { $_.Name -eq '3fa102e9-1a62-5490-7af8-6088c2f9e6be' })
  $spb=@($providers | Where-Object { $_.Name -eq '72cd9ff7-4af8-4b89-aede-5f26fda13567' })
  if($touch.Count -ne 1 -or $spb.Count -ne 1){throw 'Profile missing expected TouchAndPen / SPB providers'}
  $source=Get-Content -LiteralPath $Pointer -Raw
  if($source -notmatch 'PHYSICAL_TWO_MARK'){throw 'This pointer logger has no M-annotation support'}
  if($PhysicalTruthMode -and $source -notmatch 'SECOND_INTENTIONALLY_LIFTED'){
    throw 'This pointer logger is missing the controlled physical-truth V3 mode'
  }
}
function Assert-Admin {
  $id=[Security.Principal.WindowsIdentity]::GetCurrent()
  $pr=[Security.Principal.WindowsPrincipal]::new($id)
  if(-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run Windows PowerShell as Administrator. No driver changes will occur.'
  }
}
function Run-Command {
  param([string]$Exe,[string[]]$Argv,[string]$Log)
  $lines=& $Exe @Argv 2>&1
  $exit=$LASTEXITCODE
  $lines | Out-File -LiteralPath $Log -Encoding utf8 -Width 1200
  if($exit -ne 0){throw "$Exe exited with $exit. See $Log"}
}
function Stamp {return [DateTimeOffset]::UtcNow.ToString('o')}
function Mark {
  param([string]$Name)
  $time=Stamp
  ($time+[char]9+$Name) | Add-Content -LiteralPath (Join-Path $RunDir 'coordinator-markers.tsv')
  Write-Host "$time $Name"
}
function Manifest {
  if(-not (Test-Path -LiteralPath $RunDir)){return}
  $target=Join-Path $RunDir 'manifest.json'
  $records=@()
  foreach($f in @(Get-ChildItem -LiteralPath $RunDir -File -Recurse | Where-Object { $_.FullName -ne $target } | Sort-Object FullName)){
    $sha=$null
    try{$sha=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    catch{Write-Warning "Could not hash $($f.Name)"}
    $records += [pscustomobject]@{file=$f.FullName.Substring($RunDir.Length).TrimStart('\');bytes=$f.Length;sha256=$sha}
  }
  [pscustomobject]@{
    generated_utc=(Stamp);mode=$Mode;
    wpr_profile_sha256=(Get-FileHash -LiteralPath $Profile -Algorithm SHA256).Hash.ToLowerInvariant();
    pointer_v2_sha256=(Get-FileHash -LiteralPath $Pointer -Algorithm SHA256).Hash.ToLowerInvariant();
    pointer_protocol=$(if($PhysicalTruthMode){'V3_PHYSICAL_TRUTH'}else{'V2_PINCH'});
    files=$records;
    warning='Enabling SPB providers does not guarantee complete raw 0x0C heatmaps. Verify decoded frames.'
  } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $target -Encoding utf8
}

Assert-Assets
if($Mode -eq 'SelfTest'){
  Write-Host 'PASS: Both tools exist, profile XML parsed, SPB + TouchAndPen GUIDs and V2 M annotation present.'
  return
}
Assert-Admin
if(-not (Get-Command wpr.exe -ErrorAction SilentlyContinue)){throw 'wpr.exe is unavailable'}
if($Mode -eq 'Preflight'){
  $log=Join-Path $env:TEMP 'sl4a-pinch-wpr-preflight.log'
  Run-Command 'wpr.exe' @('-profiles',$Profile) $log
  Write-Host 'PASS: WPR accepted trace profile. Raw 0x0C frame coverage remains unverified.'
  return
}
if(-not $RunDir){
  if($Mode -eq 'Export'){throw 'Export requires -RunDir from a previous capture'}
  $name=$(if($PhysicalTruthMode){'SL4A-PhysicalTruth-'}else{'SL4A-Correlated-'})+(Get-Date -Format 'yyyyMMdd-HHmmss')
  $RunDir=Join-Path ([Environment]::GetFolderPath('Desktop')) $name
}
$RunDir=[IO.Path]::GetFullPath($RunDir)
$Etl=Join-Path $RunDir 'pinch-runtime.etl'
$Csv=Join-Path $RunDir 'pinch-runtime.csv'
$PointerOut=Join-Path $RunDir 'pointer'
if($Mode -eq 'Capture'){
  if(Test-Path -LiteralPath $RunDir){throw "Capture folder already exists: $RunDir"}
  New-Item -Path $RunDir -ItemType Directory -ErrorAction Stop | Out-Null
  New-Item -Path $PointerOut -ItemType Directory -ErrorAction Stop | Out-Null
  Copy-Item -LiteralPath $Profile -Destination (Join-Path $RunDir 'capture-profile.wprp')
  $started=$false
  $stopOk=$false
  $childExit=0
  $failure=$null
  try {
    Mark 'PREFLIGHT'
    $drive=[IO.Path]::GetPathRoot($RunDir).Substring(0,1)
    if((Get-PSDrive -Name $drive).Free -lt 2GB){throw 'At least 2 GB free space is required'}
    Run-Command 'wpr.exe' @('-profiles',$Profile) (Join-Path $RunDir 'wpr-profiles.log')
    Mark 'WPR_START_ATTEMPT'
    # Never cancel existing WPR sessions. A conflicting start fails safely.
    Run-Command 'wpr.exe' @('-start',$Profile,'-filemode') (Join-Path $RunDir 'wpr-start.log')
    $started=$true
    Mark 'WPR_ACTIVE'
    Write-Host ''
    Write-Host $(if($PhysicalTruthMode){'TRACE RECORDING. Physical-truth V3 opens: SPACE steps, B/T both, L lift, R return, N none, X invalid.'}else{'TRACE RECORDING. V2 opens now. SPACE advances stages; press M only if physically two fingers are down but display says one.'})
    Write-Host 'Finish V2 with SPACE or ESC. The trace will stop automatically.'
    $pointerArgs=@('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',$Pointer,'-OutputFolder',$PointerOut)
    if($PhysicalTruthMode){$pointerArgs+='-PhysicalTruthMode'}
    & (Join-Path $PSHOME 'powershell.exe') @pointerArgs 2>&1 |
      Tee-Object -FilePath (Join-Path $RunDir 'pointer-process.log')
    $childExit=$LASTEXITCODE
    Mark ('POINTER_EXIT_'+$childExit)
  } catch {
    $failure=$_.Exception.Message
    Write-Warning $failure
    Mark 'ERROR_RECORDED'
  } finally {
    if($started){
      try {
        Mark 'WPR_STOP_ATTEMPT'
        Run-Command 'wpr.exe' @('-stop',$Etl) (Join-Path $RunDir 'wpr-stop.log')
        $stopOk=Test-Path -LiteralPath $Etl -PathType Leaf
        Mark 'WPR_STOPPED'
      } catch {
        $failure="$failure; stop failed: $($_.Exception.Message)"
        Write-Warning $failure
      }
    }
    Manifest
  }
  if(-not $started){throw "Trace did not start; see $RunDir. $failure"}
  if(-not $stopOk){throw "Trace could not be preserved; see $RunDir. $failure"}
  if($childExit -ne 0){throw "V2 exited with code $childExit; ETL still saved: $Etl"}
  if($failure){throw "Capture failed but ETL was preserved. $failure"}
  Write-Host "Original ETL saved: $Etl"
}
if(-not (Test-Path -LiteralPath $Etl -PathType Leaf)){throw "No ETL file: $Etl"}
if($SkipCsvExport){
  Manifest
  Write-Host "ETL saved. Export later with -Mode Export -RunDir '$RunDir'"
  return
}
if($Mode -eq 'Export' -and (Test-Path -LiteralPath $Csv)){throw "CSV already exists: $Csv"}
Mark 'CSV_EXPORT_START'
try{
  Run-Command 'tracerpt.exe' @($Etl,'-o',$Csv,'-of','CSV','-rts','-y') (Join-Path $RunDir 'tracerpt.log')
  Mark 'CSV_EXPORT_COMPLETE'
}catch{
  Mark 'CSV_EXPORT_FAILED'
  Write-Warning "CSV export failed, but ETL preserved: $($_.Exception.Message)"
}
Manifest
Write-Host ''
Write-Host "SAVED $RunDir"
Write-Host 'Retain original ETL; upload manifest.json, pointer folder, and pinch-runtime.csv if practical.'
Write-Host 'WARNING: only a decoded sensor frame validates availability of 0x0C raw data.'
