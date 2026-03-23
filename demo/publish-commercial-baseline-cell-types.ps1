[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [string]$PublisherId,

    [Parameter(Mandatory = $true)]
    [string]$SourceVersion,

    [Parameter(Mandatory = $true)]
    [string]$RegistryUrl,

    [Parameter(Mandatory = $true)]
    [string]$ApiKey,

    [string]$ApiKeyHeader = "X-Battinfo-API-Key",

    [string]$OutDir
)

$ErrorActionPreference = "Stop"

$records = @(
    @{ RecordId = "a123-anr26650m1-b-2012"; Title = "A123 ANR26650M1-B" },
    @{ RecordId = "energizer-cr2032-2024"; Title = "Energizer CR2032" },
    @{ RecordId = "google-g20m7-2025"; Title = "Google G20M7" },
    @{ RecordId = "samsung-eb-ba156aby-2025"; Title = "Samsung EB-BA156ABY" },
    @{ RecordId = "samsung-eb-bs931abe-2025"; Title = "Samsung EB-BS931ABE" },
    @{ RecordId = "sunwoda-bm68-2024"; Title = "Sunwoda BM68" }
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$publishScript = Join-Path $repoRoot "scripts\publish-curated-cell-type.ps1"

if (-not (Test-Path -LiteralPath $publishScript)) {
    throw "Publish wrapper not found at '$publishScript'."
}

if (-not [string]::IsNullOrWhiteSpace($OutDir)) {
    $resolvedOutDir = if ([System.IO.Path]::IsPathRooted($OutDir)) {
        [System.IO.Path]::GetFullPath($OutDir)
    }
    else {
        [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutDir))
    }
    New-Item -ItemType Directory -Force -Path $resolvedOutDir | Out-Null
}

foreach ($record in $records) {
    $recordId = [string]$record.RecordId
    $title = [string]$record.Title
    Write-Host "Publishing $recordId"

    $args = @{
        InputPath      = $recordId
        ProjectId      = $ProjectId
        PublisherId    = $PublisherId
        SourceVersion  = $SourceVersion
        RegistryUrl    = $RegistryUrl
        ApiKey         = $ApiKey
        ApiKeyHeader   = $ApiKeyHeader
        Title          = $title
        Format         = "json"
    }

    if ($resolvedOutDir) {
        $args.OutPath = Join-Path $resolvedOutDir "$recordId.submission.summary.json"
    }

    & $publishScript @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
