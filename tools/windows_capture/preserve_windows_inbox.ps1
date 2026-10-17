# Surface Laptop 4 AMD MSHW0231: preserve exact installed Windows touch-stack binaries.
# READ-ONLY for Windows directories and registry. Writes copies and hashes to Desktop.
# Run from an elevated Windows PowerShell if file permissions require it.
# Do NOT commit the resulting .zip/binaries to a public repository.
[CmdletBinding()]
param(
  [string]$DestinationRoot = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'SL4A-windows-binary-evidence')
)
$ErrorActionPreference = 'Stop'
$sourceDir = Join-Path $DestinationRoot ('capture-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null

$files = @(
  [pscustomobject]@{ Name='HeatCore.dll'; Path=(Join-Path $env:windir 'System32\HeatCore.dll') },
  [pscustomobject]@{ Name='hidspi.sys'; Path=(Join-Path $env:windir 'System32\drivers\hidspi.sys') },
  [pscustomobject]@{ Name='HidSpiCx.sys'; Path=(Join-Path $env:windir 'System32\drivers\HidSpiCx.sys') },
  [pscustomobject]@{ Name='amdspi.sys'; Path=(Join-Path $env:windir 'System32\drivers\amdspi.sys') },
  [pscustomobject]@{
    Name='TouchPenProcessor0C19.dll'
    Path=(Join-Path $env:windir 'System32\DriverStore\FileRepository\surfacetouchpenprocessorupdate.inf_amd64_2f7c805dc6a4f0fa\TouchPenProcessor0C19.dll')
  }
)

$inventory = @(
  foreach ($entry in $files) {
    if (-not (Test-Path -LiteralPath $entry.Path -PathType Leaf)) {
      Write-Warning ("NOT FOUND: " + $entry.Path)
      [pscustomobject]@{
        Name=$entry.Name; SourcePath=$entry.Path; Status='not-found'
        Bytes=$null; Version=$null; SHA256=$null; SignatureStatus=$null; CopyPath=$null
      }
      continue
    }
    $item = Get-Item -LiteralPath $entry.Path
    $originalHash = (Get-FileHash -LiteralPath $entry.Path -Algorithm SHA256).Hash
    $copyPath = Join-Path $sourceDir $entry.Name
    Copy-Item -LiteralPath $entry.Path -Destination $copyPath -ErrorAction Stop
    $copyHash = (Get-FileHash -LiteralPath $copyPath -Algorithm SHA256).Hash
    if ($originalHash -ne $copyHash) {
      throw ('SHA256 mismatch copying: ' + $entry.Path)
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $entry.Path
    [pscustomobject]@{
      Name=$entry.Name; SourcePath=$item.FullName; Status='copied-verified'
      Bytes=$item.Length; Version=$item.VersionInfo.FileVersion
      SHA256=$originalHash; SignatureStatus=[string]$signature.Status
      CopyPath=$copyPath
    }
  }
)
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $sourceDir 'manifest.json') -Encoding UTF8
$inventory | Export-Csv -LiteralPath (Join-Path $sourceDir 'manifest.csv') -NoTypeInformation

try {
  $devices = @(Get-CimInstance Win32_PnPSignedDriver -ErrorAction Stop |
    Where-Object { $_.DeviceID -match 'MSHW0231|AMDI0060' } |
    Select-Object DeviceName,DeviceID,InfName,DriverVersion,DriverProviderName,DriverDate)
  $devices | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $sourceDir 'pnp-mshw0231-amdi0060.json') -Encoding UTF8
}
catch {
  Write-Warning ('PnP inventory unavailable: ' + $_.Exception.Message)
}

$zip = $sourceDir + '.zip'
Compress-Archive -LiteralPath $sourceDir -DestinationPath $zip -Force
$inventory | Format-Table Name,Status,Bytes,Version,SHA256 -AutoSize
Write-Host ('Evidence folder: ' + $sourceDir)
Write-Host ('Evidence archive: ' + $zip)
Write-Host 'Do not install these copies or commit Microsoft binaries into a public Git repo.'
