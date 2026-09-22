param(
    [string]$Etl = "C:\\gate2\\gate2.etl",
    [string]$OutDir = "C:\\gate2\\decode"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not (Test-Path $Etl)) {
    throw "ETL not found: $Etl"
}

$hash = (Get-FileHash -Algorithm SHA256 $Etl).Hash.ToLowerInvariant()
@{
    etl = $Etl
    sha256 = $hash
    bytes = (Get-Item $Etl).Length
    exported_utc = [DateTimeOffset]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $OutDir "etl-export-manifest.json")

$xml = Join-Path $OutDir "gate2.xml"
$csv = Join-Path $OutDir "gate2.csv"
$summary = Join-Path $OutDir "gate2-summary.txt"
$report = Join-Path $OutDir "gate2-report.xml"

& tracerpt.exe $Etl -o $xml -of XML -lr -summary $summary -report $report -y 2>&1 |
    Tee-Object -FilePath (Join-Path $OutDir "tracerpt-xml.log")
if ($LASTEXITCODE -ne 0) {
    throw "tracerpt XML export failed with exit code $LASTEXITCODE"
}

& tracerpt.exe $Etl -o $csv -of CSV -lr -rts -y 2>&1 |
    Tee-Object -FilePath (Join-Path $OutDir "tracerpt-csv.log")
if ($LASTEXITCODE -ne 0) {
    throw "tracerpt CSV export failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Gate 2 ETL export complete."
Write-Host "ETL SHA256: $hash"
Write-Host "Outputs:"
Write-Host "  $xml"
Write-Host "  $csv"
Write-Host "  $summary"
Write-Host "  $report"
Write-Host ""
Write-Host "Zip C:\\gate2 again and upload it. No recapture is required."
