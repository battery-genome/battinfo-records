[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias("Input")]
    [string]$InputPath,

    # Optional override. By default the curated id is taken from the dataset record's
    # own identifier (e.g. "bdc:bdc_000001" -> "bdc_000001").
    [string]$RecordId,

    [string]$ValidationPolicy = "default",

    [ValidateSet("json", "table")]
    [string]$Format = "table",

    [string]$StagingRoot,

    [string]$CuratedRoot,

    [string]$BattinfoExe,

    [switch]$DryRun,

    [switch]$DeleteStagingOnSuccess
)

$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)] [string]$PathValue,
        [Parameter(Mandatory = $true)] [string]$BasePath
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
$repoRoot = if ([string]::IsNullOrWhiteSpace($repoRoot)) { (Get-Location).Path } else { $repoRoot }
$parentRoot = Split-Path -Parent $repoRoot

if ([string]::IsNullOrWhiteSpace($StagingRoot)) {
    $StagingRoot = Join-Path $repoRoot "records\_staging\dataset"
}
if ([string]::IsNullOrWhiteSpace($CuratedRoot)) {
    $CuratedRoot = Join-Path $repoRoot "records\dataset"
}
if ([string]::IsNullOrWhiteSpace($BattinfoExe)) {
    $BattinfoExe = Join-Path $parentRoot "BattINFO\.venv\Scripts\battinfo.exe"
}

$resolvedStagingRoot = Resolve-AbsolutePath -PathValue $StagingRoot -BasePath $repoRoot
$resolvedCuratedRoot = Resolve-AbsolutePath -PathValue $CuratedRoot -BasePath $repoRoot
$resolvedBattinfoExe = Resolve-AbsolutePath -PathValue $BattinfoExe -BasePath $repoRoot

if (-not (Test-Path -LiteralPath $resolvedBattinfoExe)) {
    throw "BattINFO CLI not found at '$resolvedBattinfoExe'."
}

if ([System.IO.Path]::IsPathRooted($InputPath)) {
    $resolvedInput = Resolve-AbsolutePath -PathValue $InputPath -BasePath $repoRoot
}
else {
    $candidate = Resolve-AbsolutePath -PathValue $InputPath -BasePath (Get-Location).Path
    if (Test-Path -LiteralPath $candidate) {
        $resolvedInput = $candidate
    }
    else {
        $resolvedInput = Resolve-AbsolutePath -PathValue $InputPath -BasePath $resolvedStagingRoot
    }
}

if (-not (Test-Path -LiteralPath $resolvedInput)) {
    throw "Staging input not found at '$resolvedInput'."
}

$validateArgs = @(
    "editorial",
    "validate-staging-dataset",
    "--input", $resolvedInput,
    "--validation-policy", $ValidationPolicy,
    "--format", "json"
)

$validationJson = & $resolvedBattinfoExe @validateArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$validation = $validationJson | ConvertFrom-Json

# The curated id comes from the record itself unless the caller overrides it. If the
# record has no safe automatic id and none was supplied, fail with a clear message.
$manualRecordId = -not [string]::IsNullOrWhiteSpace($RecordId)
if (-not $manualRecordId -and [bool]$validation.requires_record_id) {
    throw "This staging dataset has no safe automatic record id. Provide -RecordId (suggested pattern: $($validation.record_id_hint))."
}

$promoteArgs = @(
    "editorial",
    "promote-staging-dataset",
    "--input", $resolvedInput,
    "--curated-root", $resolvedCuratedRoot,
    "--validation-policy", $ValidationPolicy,
    "--format", $Format
)

if ($manualRecordId) {
    $promoteArgs += @("--record-id", $RecordId)
}

if ($DryRun) {
    $promoteArgs += "--dry-run"
}

$reportedId = if ($manualRecordId) { $RecordId } else { $validation.record_id }
Write-Host "Using record id: $reportedId"
& $resolvedBattinfoExe @promoteArgs
$exitCode = $LASTEXITCODE

if (
    $exitCode -eq 0 -and
    -not $DryRun -and
    $DeleteStagingOnSuccess -and
    (Test-Path -LiteralPath $resolvedInput -PathType Leaf)
) {
    $stagingRootWithSeparator = [System.IO.Path]::TrimEndingDirectorySeparator($resolvedStagingRoot) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolvedInput.StartsWith($stagingRootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedInput
        Write-Host "Deleted staging draft: $resolvedInput"
    }
    else {
        Write-Warning "DeleteStagingOnSuccess was requested, but '$resolvedInput' is outside staging root '$resolvedStagingRoot'. Skipping delete."
    }
}

exit $exitCode
