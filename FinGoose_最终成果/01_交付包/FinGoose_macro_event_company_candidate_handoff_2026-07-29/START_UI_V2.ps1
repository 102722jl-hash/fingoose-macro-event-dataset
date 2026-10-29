param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8782
)

$packageRoot = $PSScriptRoot
$env:PYTHONPATH = Join-Path $packageRoot "code"

python (Join-Path $packageRoot "code\fingoose_macro_event_v2_dashboard.py") `
    --data-root (Join-Path $packageRoot "data\market_event_attribution_v2_candidate") `
    --config-path (Join-Path $packageRoot "configs\fingoose_macro_events_v1.json") `
    --host $HostAddress `
    --port $Port
