# MySQL Company Enhancement Candidate Design

Date: 2026-07-31

## Scope

Build an isolated, read-only MySQL enhancement bundle for the existing 30 company candidates. The bundle covers only:

1. company-to-industry candidate mapping;
2. analyst-rating windows around the event anchor;
3. company financial baselines available before the observation cutoff.

It does not modify UI files, production v2 data, existing company candidate files, MySQL tables, permissions, or indexes.

## Inputs

- `data/company_candidate_v1/candidate_company_registry.jsonl`
- `work/transmission_24_anchor_v2_candidate/anchor_catalog.jsonl`
- MySQL database `workspace`, accessed through login path `fingoose-codex`
- Industry membership tables matching `fr_*_history`
- `asharestockratingconsus_202607231014`
- `asharebalancesheet_202605261517`
- `ashareincome_202605261519`
- `asharecashflow_202605261518`

## Outputs

The builder writes only to `work/mysql_company_enhancement_v1_candidate/`:

- `company_impact_candidates.jsonl`: existing event/company pairs enriched with candidate industry membership and event impact tags. Industry membership is vendor metadata, while exposure and direction remain `PROPOSED_UNVERIFIED`.
- `company_rating_windows.jsonl`: deduplicated rating observations from 60 calendar days before through 60 calendar days after the selected event anchor, with separate pre/post summaries and explicit missing-data status.
- `company_financial_baselines.jsonl`: the latest balance-sheet, income-statement, and cash-flow records whose announcement date is not later than the event anchor date. Missing history remains `UNKNOWN`.
- `source_manifest.jsonl`: MySQL table provenance, query purpose, coverage, license status, and redistribution restrictions without credentials or raw SQL secrets.
- `validation_report.json`: record counts, uniqueness checks, cutoff leakage checks, missing coverage, hard failures, and warnings.
- `summary.json`: release tier, usable counts, blockers, and `formal_ready=false`.
- `manifest.json`: SHA-256 and record count for every emitted file.
- `README.md`: usage and limitations.

## Data Rules

- MySQL access is read-only and uses `mysql.exe --login-path=fingoose-codex`.
- No password, login-path file, or credential material is copied into outputs.
- The primary event anchor is the earliest `CAUSAL_CANDIDATE` record with `node_action=STARTS`; if unavailable, the company record is emitted with `ANCHOR_UNKNOWN`.
- Industry membership is derived from membership in one `fr_*_history` table. Zero matches produce `UNKNOWN`; multiple matches produce `AMBIGUOUS` and a validation warning.
- Rating source rows are deduplicated by the full published payload before summary calculation. Multiple distinct same-day payloads remain visible as separate observations; no arbitrary averaging across incompatible cycles is allowed.
- Financial baselines use `actual_ann_dt` when present, otherwise `ann_dt`. Records announced after the event anchor are excluded to prevent leakage.
- Vendor data may support candidate screening and quantitative context, but never upgrades official company exposure evidence.

## Release Boundary

- `release_tier=VENDOR_CANDIDATE`
- `formal_ready=false`
- `display_allowed=false`
- `redistribution_allowed=false`
- `official_company_exposure_verified=false`
- No existing production or UI file is modified.

## Acceptance

- Exactly 30 company impact candidates are emitted.
- Every candidate has one anchor-status field, one industry-status field, and a vendor-source reference.
- Rating windows cover all 30 candidates, including explicit `NO_WINDOW_DATA` records.
- Financial baselines cover all 30 candidates, including explicit `NO_PRE_EVENT_DATA` records.
- No financial record has an effective announcement date later than the event anchor date.
- Output IDs are unique, JSON/JSONL parses, hashes recompute, and validation reports no hard failure.

