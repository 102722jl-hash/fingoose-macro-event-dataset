# Event Industry, Price Window, and Timeline Gap Candidate Design

## Scope

Build three isolated candidate bundles without changing production v2, existing timeline candidates, existing transmission candidates, company candidates, or UI files.

1. Join the fixed 24-anchor catalog and proposed transmission graphs to the 30-company MySQL candidate layer.
2. Fetch and normalize adjusted A-share daily bars for all 30 event-company pairs from the Eastmoney public endpoint.
3. Re-audit the eight `PENDING_EVIDENCE` timeline nodes against existing local source snapshots.

## Release Boundaries

- Industry/company impacts remain `PROPOSED_CONDITIONAL` or `UNKNOWN`.
- Public price windows remain `PUBLIC_VENDOR_CANDIDATE`; they are observational and cannot establish causality.
- Timeline nodes are promoted only when a semantically matched snapshot independently supports fact, `occurred_at`, `first_public_at`, locator, and snapshot hash.
- MySQL access remains read-only. No public vendor payload is represented as official evidence.
- All bundles use `formal_ready=false` and `causal_attribution_allowed=false`.

## Outputs

- `work/event_industry_impact_v1_candidate/`
- `work/company_price_windows_public_vendor_v1_candidate/`
- `work/timeline_gap_resolution_v1_candidate/`

Each bundle includes records, a validation report, a summary, a README, and a SHA-256 manifest. Price windows additionally preserve normalized response snapshots.

## Price Window Rules

- Shanghai tickers map to `secid=1.<code>` and Shenzhen tickers to `secid=0.<code>`.
- Use daily K lines (`klt=101`) with forward adjustment (`fqt=1`).
- T0 is the first trading date on or after the anchor date.
- T-1 is the immediately preceding available trading day.
- D1, D3, D5, and D20 are trading-session offsets from T0.
- Every observation stores date, close, raw return from T-1, and missing status. No calendar-day imputation is permitted.

## Validation

- Counts and IDs must be unique and match the 30 company pairs / 8 gaps.
- Industry direction may only inherit a pre-event proposed graph path; post-event price returns cannot set direction.
- Price snapshots must be parseable and hashed; missing API data remains explicit.
- Pending evidence cannot be promotion eligible.
- Production milestone, episode, and manifest hashes must remain unchanged.
