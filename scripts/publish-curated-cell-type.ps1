[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias("Input")]
    [string]$InputPath,

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

    [string]$Title,

    [string]$ValidationPolicy = "default",

    [ValidateSet("json", "table")]
    [string]$Format = "table",

    [string]$CuratedRoot,

    [string]$BattinfoExe,

    [string]$OutPath
)

$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,

        [Parameter(Mandatory = $true)]
        [string]$BasePath
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $PathValue))
}

$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot) -and -not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
    $scriptRoot = Split-Path -Parent $PSCommandPath
}
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = (Get-Location).Path
}

$repoRoot = Split-Path -Parent $scriptRoot
$parentRoot = Split-Path -Parent $repoRoot

if ([string]::IsNullOrWhiteSpace($CuratedRoot)) {
    $CuratedRoot = Join-Path $repoRoot "records\cell-types"
}
if ([string]::IsNullOrWhiteSpace($BattinfoExe)) {
    $BattinfoExe = Join-Path $parentRoot "BattINFO\.venv\Scripts\battinfo.exe"
}

$resolvedCuratedRoot = Resolve-AbsolutePath -PathValue $CuratedRoot -BasePath $repoRoot
$resolvedBattinfoExe = Resolve-AbsolutePath -PathValue $BattinfoExe -BasePath $repoRoot

if (-not (Test-Path -LiteralPath $resolvedBattinfoExe)) {
    throw "BattINFO CLI not found at '$resolvedBattinfoExe'."
}

$resolvedInput = $null
if ([System.IO.Path]::IsPathRooted($InputPath)) {
    $resolvedInput = Resolve-AbsolutePath -PathValue $InputPath -BasePath $repoRoot
}
else {
    $candidate = Resolve-AbsolutePath -PathValue $InputPath -BasePath (Get-Location).Path
    if (Test-Path -LiteralPath $candidate) {
        $resolvedInput = $candidate
    }
    else {
        $recordJsonCandidate = Join-Path (Join-Path $resolvedCuratedRoot $InputPath) "record.json"
        if (Test-Path -LiteralPath $recordJsonCandidate) {
            $resolvedInput = [System.IO.Path]::GetFullPath($recordJsonCandidate)
        }
    }
}

if (-not $resolvedInput) {
    throw "Could not resolve curated input '$InputPath'. Provide a record id, a record directory, or a path to record.json."
}
if (-not (Test-Path -LiteralPath $resolvedInput)) {
    throw "Curated input not found at '$resolvedInput'."
}

$args = @(
    "editorial",
    "publish-curated-cell-type",
    "--input", $resolvedInput,
    "--project-id", $ProjectId,
    "--publisher-id", $PublisherId,
    "--source-version", $SourceVersion,
    "--registry-url", $RegistryUrl,
    "--api-key", $ApiKey,
    "--api-key-header", $ApiKeyHeader,
    "--validation-policy", $ValidationPolicy,
    "--format", $Format
)

if (-not [string]::IsNullOrWhiteSpace($Title)) {
    $args += @("--title", $Title)
}
if (-not [string]::IsNullOrWhiteSpace($OutPath)) {
    $resolvedOutPath = Resolve-AbsolutePath -PathValue $OutPath -BasePath $repoRoot
    $args += @("--out", $resolvedOutPath)
}

& $resolvedBattinfoExe @args
exit $LASTEXITCODE
