$ErrorActionPreference = "Stop"
$packageRoot = $PSScriptRoot

function Read-JsonLines([string]$Path) {
    return @(Get-Content -LiteralPath $Path -Encoding UTF8 | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
}

$marketRoot = Join-Path $packageRoot "data\market_event_attribution_v1"
$companyRoot = Join-Path $packageRoot "data\company_enriched_candidate_v1"
$marketSummary = Get-Content -LiteralPath (Join-Path $marketRoot "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$companySummary = Get-Content -LiteralPath (Join-Path $companyRoot "summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json

if ($marketSummary.event_count -ne 10 -or $marketSummary.sample_count -ne 40) {
    throw "Market count verification failed."
}
if ($companySummary.event_count -ne 10 -or $companySummary.company_dossier_count -ne 30 -or $companySummary.candidate_sample_count -ne 60) {
    throw "Company count verification failed."
}
if (-not $marketSummary.formal_ready) {
    throw "Market release should be formal_ready=true."
}
if ($companySummary.formal_ready -or -not $companySummary.candidate_ready -or $companySummary.release_tier -ne "CANDIDATE") {
    throw "Company candidate/formal status verification failed."
}

$manifestPath = Join-Path $packageRoot "FILE_MANIFEST.csv"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "FILE_MANIFEST.csv is missing."
}

$manifest = Import-Csv -LiteralPath $manifestPath
foreach ($row in $manifest) {
    $filePath = Join-Path $packageRoot $row.relative_path
    if (-not (Test-Path -LiteralPath $filePath)) {
        throw "Manifest file is missing: $($row.relative_path)"
    }
    $actual = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $row.sha256) {
        throw "SHA-256 mismatch: $($row.relative_path)"
    }
}

Write-Host "HANDOFF VERIFIED" -ForegroundColor Green
Write-Host "Events=10 MarketSamples=40 CompanyDossiers=30 CompanySamples=60"
Write-Host "Market formal_ready=true; Company candidate_ready=true formal_ready=false"
