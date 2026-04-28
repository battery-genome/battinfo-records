<#
.SYNOPSIS
Republishes the 52 cell-type records that received publication links.

.EXAMPLE
  $env:BATTINFO_API_KEY = "your-key-here"
  .\scripts\publish-publications-batch.ps1
#>

param(
    [string]$ApiKey       = $env:BATTINFO_API_KEY,
    [string]$RegistryUrl  = "https://battinfo-registry.onrender.com",
    [string]$ProjectId    = "battinfo-records",
    [string]$PublisherId  = "battinfo-records-bot",
    [string]$SourceVersion = "2026-04-28-citations"
)

if (-not $ApiKey) {
    Write-Error "Set BATTINFO_API_KEY or pass -ApiKey"
    exit 1
}

$scriptDir   = $PSScriptRoot
$repoRoot    = Split-Path -Parent $scriptDir
$publishScript = Join-Path $scriptDir "publish-curated-cell-type.ps1"

$records = @(
    "a123--amp20m1hd-a--20260324",
    "bak--n21700cg-50--20260324",
    "calb--ca60--20260324",
    "calb--cam72--20260324",
    "calb--l135f72-cam72--20260324",
    "eagle-picher-technologies-llc--lp-32770--20260324",
    "eagle-picher-technologies-llc--lp-33450--20260324",
    "gaia--hp-602030--20260324",
    "gs-yuasa-technology--lvp10--20260324",
    "kokam--slpb065070180--20260324",
    "kokam--slpb080085270--20260324",
    "kokam--slpb100216216h--20260324",
    "kokam--slpb11543140h5--20260324",
    "kokam--slpb120216216--20260324",
    "kokam--slpb120216216g1--20260324",
    "kokam--slpb120216216g1h--20260324",
    "kokam--slpb120216216g2--20260324",
    "kokam--slpb120216216hr2--20260324",
    "kokam--slpb120255255--20260324",
    "kokam--slpb125255255h--20260324",
    "kokam--slpb50106100--20260324",
    "kokam--slpb55205130h--20260324",
    "kokam--slpb75106100--20260324",
    "kokam--slpb75106205--20260324",
    "kokam--slpb78216216h--20260324",
    "kokam--slpb90216216--20260324",
    "lg--e63--20260324",
    "lg--e63b--20260324",
    "lg--e66a--20260324",
    "lg--inr18650-mj1--20260324",
    "lg--inr21700-m50--20260324",
    "lg--inr21700-m50t--20260324",
    "lishen--lr2170sa--20260324",
    "molicel--inr-21700-p42a--2000",
    "murata--us21700vtc6a--20260324",
    "panasonic--ncr18650bf--20260324",
    "panasonic--ncr20700b--20260324",
    "quallion-llc--ql015ka--20260324",
    "saft--mp176065--20260324",
    "saft--mp176065xtd--20260324",
    "saft--ves180--20260324",
    "saft--vl-41m--20260324",
    "saft--vl-45e--20260324",
    "saft--vl-45e-fe--20260324",
    "samsung--inr21700-30t--20260324",
    "samsung--inr21700-40t--2017",
    "samsung--inr21700-48g--2015",
    "samsung--inr21700-48x--2019",
    "samsung--inr21700-50e--2017",
    "samsung--sdi-94ah--20260324",
    "thunder-sky--wb-lyp100aha--20260324",
    "thunder-sky--wb-lyp40aha--20260324"
)

$ok   = 0
$fail = 0

foreach ($id in $records) {
    Write-Host -NoNewline "Publishing $id ... "
    $null = & $publishScript `
        -InputPath    $id `
        -ProjectId    $ProjectId `
        -PublisherId  $PublisherId `
        -SourceVersion $SourceVersion `
        -RegistryUrl  $RegistryUrl `
        -ApiKey       $ApiKey `
        -Format       table 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "ok" -ForegroundColor Green
        $ok++
    } else {
        Write-Host "FAILED (exit $exitCode)" -ForegroundColor Red
        $fail++
    }
}

Write-Host "`nDone: $ok published, $fail failed"
