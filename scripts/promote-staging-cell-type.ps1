[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias("Input")]
    [string]$InputPath,

    [string]$RecordId,

    [string]$Year,

    [string]$Revision,

    [string]$EvidenceDate,

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

function Normalize-RecordToken {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim().ToLowerInvariant()
    $normalized = [System.Text.RegularExpressions.Regex]::Replace($normalized, "[^a-z0-9]+", "-")
    $normalized = [System.Text.RegularExpressions.Regex]::Replace($normalized, "-+", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        throw "Could not derive a record-id token from '$Value'."
    }
    return $normalized
}

function Normalize-RecordId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $segments = $Value -split "-{2,}" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($segments.Count -eq 0) {
        throw "Could not derive a record id from '$Value'."
    }
    return (($segments | ForEach-Object { Normalize-RecordToken -Value $_ }) -join "--")
}

function Normalize-EvidenceDateToken {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $trimmed = $Value.Trim()
    if ($trimmed -match "^\d{8}$") {
        return $trimmed
    }
    if ($trimmed -match "^\d{4}-\d{2}-\d{2}$") {
        return $trimmed.Replace("-", "")
    }
    try {
        return [DateTimeOffset]::Parse($trimmed).ToString("yyyyMMdd")
    }
    catch {
        throw "EvidenceDate must be YYYYMMDD or a parseable date/time string."
    }
}

function Get-StagingRecordParts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonPath
    )

    $record = Get-Content -LiteralPath $JsonPath -Raw | ConvertFrom-Json

    if ($null -ne $record.product) {
        $manufacturer = [string]$record.product.manufacturer.name
        $model = [string]$record.product.model
        if ([string]::IsNullOrWhiteSpace($model)) {
            $model = [string]$record.product.name
        }
        $year = [string]$record.product.year
    }
    else {
        $manufacturer = [string]$record.manufacturer
        $model = [string]$record.model
        if ([string]::IsNullOrWhiteSpace($model)) {
            $model = [string]$record.name
        }
        $year = [string]$record.year
    }

    if ([string]::IsNullOrWhiteSpace($manufacturer)) {
        throw "Could not derive a manufacturer token from '$JsonPath'."
    }
    if ([string]::IsNullOrWhiteSpace($model)) {
        throw "Could not derive a model token from '$JsonPath'."
    }

    return [pscustomobject]@{
        BaseId = "$(Normalize-RecordToken -Value $manufacturer)--$(Normalize-RecordToken -Value $model)"
        Year = $year
    }
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
    $StagingRoot = Join-Path $repoRoot "records\_staging\cell-type"
}
if ([string]::IsNullOrWhiteSpace($CuratedRoot)) {
    $CuratedRoot = Join-Path $repoRoot "records\cell-type"
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
    "validate-staging-cell-type",
    "--input", $resolvedInput,
    "--validation-policy", $ValidationPolicy,
    "--format", "json"
)

$validationJson = & $resolvedBattinfoExe @validateArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$validation = $validationJson | ConvertFrom-Json

$resolvedRecordId = $null
$manualRecordId = $false
if (-not [string]::IsNullOrWhiteSpace($RecordId)) {
    $resolvedRecordId = Normalize-RecordId -Value $RecordId
    $manualRecordId = $true
}
elseif (-not [bool]$validation.requires_record_id) {
    $stagingParts = Get-StagingRecordParts -JsonPath $resolvedInput
    if (-not [string]::IsNullOrWhiteSpace($stagingParts.Year)) {
        if ($stagingParts.Year -notmatch "^\d{4}$") {
            throw "Year must be a 4-digit value."
        }
        $resolvedRecordId = "$($stagingParts.BaseId)--$($stagingParts.Year)"
    }
    else {
        $resolvedRecordId = $stagingParts.BaseId
    }
    $manualRecordId = $true
}
else {
    $stagingParts = Get-StagingRecordParts -JsonPath $resolvedInput
    $baseRecordId = $stagingParts.BaseId

    if (-not [string]::IsNullOrWhiteSpace($Year)) {
        if ($Year -notmatch "^\d{4}$") {
            throw "Year must be a 4-digit value."
        }
        $resolvedRecordId = "$baseRecordId--$Year"
        $manualRecordId = $true
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Revision)) {
        $resolvedRecordId = "$baseRecordId--$(Normalize-RecordToken -Value $Revision)"
        $manualRecordId = $true
    }
    elseif (-not [string]::IsNullOrWhiteSpace($EvidenceDate)) {
        $resolvedRecordId = "$baseRecordId--$(Normalize-EvidenceDateToken -Value $EvidenceDate)"
        $manualRecordId = $true
    }
    else {
        throw "This staging draft needs an explicit curated id. Provide -RecordId, -Year, -Revision, or -EvidenceDate. Suggested pattern: $baseRecordId--<year-or-revision>"
    }
}

$promoteArgs = @(
    "editorial",
    "promote-staging-cell-type",
    "--input", $resolvedInput,
    "--curated-root", $resolvedCuratedRoot,
    "--validation-policy", $ValidationPolicy,
    "--format", $Format
)

if ($manualRecordId) {
    $promoteArgs += @("--record-id", $resolvedRecordId)
}

if ($DryRun) {
    $promoteArgs += "--dry-run"
}

Write-Host "Using record id: $resolvedRecordId"
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
