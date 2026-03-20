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

    [switch]$DryRun
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

function Resolve-BaseRecordId {
    param(
        [Parameter(Mandatory = $true)]
        $ValidationPayload
    )

    $hint = [string]$ValidationPayload.record_id_hint
    if (-not [string]::IsNullOrWhiteSpace($hint) -and $hint -match "^(.*)-<[^>]+>$") {
        return $Matches[1]
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$ValidationPayload.record_id)) {
        $recordId = [string]$ValidationPayload.record_id
        $basis = [string]$ValidationPayload.record_id_basis
        if ($basis -eq "year" -and $recordId -match "^(.*)-\d{4}$") {
            return $Matches[1]
        }
        if ($basis -eq "evidence_date" -and $recordId -match "^(.*)-\d{8}$") {
            return $Matches[1]
        }
    }
    return $null
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
    $StagingRoot = Join-Path $repoRoot "records\_staging\cell-types"
}
if ([string]::IsNullOrWhiteSpace($CuratedRoot)) {
    $CuratedRoot = Join-Path $repoRoot "records\cell-types"
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
    $resolvedRecordId = Normalize-RecordToken -Value $RecordId
    $manualRecordId = $true
}
elseif (-not [bool]$validation.requires_record_id) {
    $resolvedRecordId = [string]$validation.record_id
}
else {
    $baseRecordId = Resolve-BaseRecordId -ValidationPayload $validation
    if ([string]::IsNullOrWhiteSpace($baseRecordId)) {
        throw "Could not derive a base record id from the validation payload."
    }

    if (-not [string]::IsNullOrWhiteSpace($Year)) {
        if ($Year -notmatch "^\d{4}$") {
            throw "Year must be a 4-digit value."
        }
        $resolvedRecordId = "$baseRecordId-$Year"
        $manualRecordId = $true
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Revision)) {
        $resolvedRecordId = "$baseRecordId-$(Normalize-RecordToken -Value $Revision)"
        $manualRecordId = $true
    }
    elseif (-not [string]::IsNullOrWhiteSpace($EvidenceDate)) {
        $resolvedRecordId = "$baseRecordId-$(Normalize-EvidenceDateToken -Value $EvidenceDate)"
        $manualRecordId = $true
    }
    else {
        throw "This staging draft needs an explicit curated id. Provide -RecordId, -Year, -Revision, or -EvidenceDate. Suggested pattern: $($validation.record_id_hint)"
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
exit $LASTEXITCODE
