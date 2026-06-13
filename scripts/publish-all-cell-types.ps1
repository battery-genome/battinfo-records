<#
.SYNOPSIS
Republishes all cell-type records to the registry.
Run this after any bulk update to records (e.g. manufacturer.id backfill).

.EXAMPLE
  $env:BATTINFO_API_KEY = "your-key-here"
  .\scripts\publish-all-cell-types.ps1

.EXAMPLE
  # Dry-run: discover records without publishing
  .\scripts\publish-all-cell-types.ps1 -DryRun
#>

param(
    [string]$ApiKey        = $env:BATTINFO_API_KEY,
    [string]$RegistryUrl   = "https://battinfo-registry.onrender.com",
    [string]$ProjectId     = "battinfo-records",
    [string]$PublisherId   = "battinfo-records-bot",
    [string]$SourceVersion = "2026-06-12-manufacturer-id",
    [string]$CuratedRoot,
    [switch]$DryRun
)

if (-not $DryRun -and -not $ApiKey) {
    Write-Error "Set BATTINFO_API_KEY or pass -ApiKey (or use -DryRun to list records only)"
    exit 1
}

$scriptDir     = $PSScriptRoot
$repoRoot      = Split-Path -Parent $scriptDir
$publishScript = Join-Path $scriptDir "publish-curated-cell-type.ps1"

if ([string]::IsNullOrWhiteSpace($CuratedRoot)) {
    $CuratedRoot = Join-Path $repoRoot "records\cell-type"
}

$recordDirs = Get-ChildItem -LiteralPath $CuratedRoot -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName "record.json") }

$total = $recordDirs.Count
Write-Host "Found $total cell-type records under $CuratedRoot"

if ($DryRun) {
    Write-Host "`nDry-run mode — listing records that would be published:"
    $recordDirs | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host "`nTotal: $total records (not published)"
    exit 0
}

$ok   = 0
$fail = 0
$i    = 0

foreach ($dir in $recordDirs) {
    $i++
    $id = $dir.Name
    Write-Host -NoNewline "[$i/$total] $id ... "

    $null = & $publishScript `
        -InputPath     $id `
        -ProjectId     $ProjectId `
        -PublisherId   $PublisherId `
        -SourceVersion $SourceVersion `
        -RegistryUrl   $RegistryUrl `
        -ApiKey        $ApiKey `
        -CuratedRoot   $CuratedRoot `
        -Format        table 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "ok" -ForegroundColor Green
        $ok++
    } else {
        Write-Host "FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $ok published, $fail failed out of $total total"
if ($fail -gt 0) { exit 1 }
