param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8778
)

$packageRoot = $PSScriptRoot
$env:PYTHONPATH = Join-Path $packageRoot "code"

python (Join-Path $packageRoot "code\fingoose_macro_event_company_deep_dashboard_v1.py") `
    --market-output-root (Join-Path $packageRoot "data\market_event_attribution_v1") `
    --company-output-root (Join-Path $packageRoot "data\company_enriched_candidate_v1") `
    --host $HostAddress `
    --port $Port

