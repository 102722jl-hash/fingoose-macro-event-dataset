# FinGoose Event-Company Dataset And Unified Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable 10-event, 30-company, 60-sample event-to-company dataset and then expose it beside the unchanged 40-sample market dataset in one read-only dashboard.

**Architecture:** Keep the company release in `outputs/fingoose_macro_event_company_v1` and treat the two existing formal output roots as read-only upstream data. A focused company domain module owns calculations, projection safety, review logic, schema validation, and release gates; a separate builder reads versioned configuration plus archived evidence and writes deterministic JSON/JSONL artifacts. The dashboard repository later joins the market and company roots without copying hidden labels into public projections.

**Tech Stack:** Python 3, standard library, `jsonschema`, existing FinGoose source/PDF helpers, `unittest`, native HTML/CSS/JavaScript, Playwright.

---

### Task 1: Company domain calculations, schemas, and leakage boundary

**Files:**
- Create: `fingoose_macro_event_company_v1.py`
- Create: `tests/test_fingoose_macro_event_company_v1.py`
- Create: `schemas/fingoose_company_event_dossier_v1.schema.json`
- Create: `schemas/fingoose_company_metric_fact_v1.schema.json`
- Create: `schemas/fingoose_company_stock_window_v1.schema.json`
- Create: `schemas/fingoose_company_attribution_sample_v1.schema.json`
- Create: `schemas/fingoose_company_forecast_sample_v1.schema.json`
- Create: `schemas/fingoose_company_review_record_v1.schema.json`

- [ ] Write failing unit tests for cumulative-quarter differencing, YoY/QoQ, unit/currency compatibility, event-session alignment, suspension/missing prices, company and CSI 300 returns, and abnormal returns.
- [ ] Run `python -m unittest tests.test_fingoose_macro_event_company_v1 -v` and confirm failures are caused by missing production APIs.
- [ ] Implement exact-decimal calculations and stock windows with `D1/D3/D5/D20`; reject incompatible metrics, units, currencies, companies, periods, and non-finite values.
- [ ] Add failing tests for company codes, source tiers, observation quarters, association/direction/forecast labels, review triggers, reviewer independence, and adjudication.
- [ ] Implement the six Draft 2020-12 schemas plus `validate_schema_record`, `company_second_review_trigger_reasons`, `company_review_errors`, and deterministic final-verdict resolution.
- [ ] Add failing leakage tests asserting forecast public data excludes future report/source IDs, actual values, `D5/D20`, next-quarter results, and retrospective conclusions.
- [ ] Implement `build_company_forecast_projection` from an independent cutoff snapshot and recursively reject hidden keys or evidence published after `forecast_as_of_at`.
- [ ] Run the focused tests and confirm zero failures.

Stable public API:

```python
derive_standalone_quarter(current_cumulative, prior_cumulative) -> dict
calculate_period_comparison(current, comparison) -> dict
compute_company_stock_window(company_observations, benchmark_observations, t0_session) -> dict
build_company_forecast_projection(cutoff_snapshot) -> dict
company_second_review_trigger_reasons(review) -> list[str]
validate_company_release(records) -> dict
```

### Task 2: Deterministic builder and pilot configuration

**Files:**
- Create: `build_fingoose_macro_event_company_v1.py`
- Create: `tests/test_build_fingoose_macro_event_company_v1.py`
- Create: `configs/fingoose_macro_event_companies_v1.json`
- Create: `configs/fingoose_macro_event_company_reviews_v1.jsonl`
- Create: `inputs/fingoose_macro_event_company_v1/`

- [ ] Write failing builder tests using a temporary three-event, nine-dossier fixture and assert exact artifact names, stable ordering, hashes, and no writes outside the selected output root.
- [ ] Confirm RED, then implement CLI arguments `--config`, `--review-decisions`, and `--output-root`.
- [ ] Require archived source snapshots with SHA-256 and locator information; source Tier 3 cannot independently support an event fact or numeric conclusion.
- [ ] Build independent public forecast inputs at event `D3`, and keep actual first-quarter, second-quarter, future source IDs, `D5/D20`, and retrospective labels only in hidden artifacts.
- [ ] Reuse the existing event-02 archived CNINFO/EIA/NATO material by reference and hash verification; do not alter its historical evidence output.
- [ ] Add pilot configuration for the fixed nine companies and refuse `formal_ready=true` if any required evidence or completed review is missing.
- [ ] Run focused builder tests and replay every generated numeric calculation from source facts.

Required output artifacts:

```text
summary.json
company_event_dossiers.jsonl
company_metric_facts.jsonl
company_stock_windows.jsonl
company_attribution_samples.jsonl
company_forecast_samples.jsonl
company_training_projection.jsonl
company_hidden_outcomes.jsonl
company_review_records.jsonl
source_manifest.jsonl
rejected.jsonl
validation_report.json
```

### Task 3: Complete and review the nine-dossier pilot

**Files:**
- Modify: `configs/fingoose_macro_event_companies_v1.json`
- Modify: `configs/fingoose_macro_event_company_reviews_v1.jsonl`
- Add only archived files under: `inputs/fingoose_macro_event_company_v1/`
- Generate only: `outputs/fingoose_macro_event_company_v1/`

- [ ] Archive official event/industry sources, company exposure disclosures, first complete quarter, next quarter, and auditable company/CSI 300 price series for event-01, event-02, and event-05.
- [ ] Record at least one competing explanation or counterevidence item per dossier.
- [ ] Generate 9 dossiers, 9 attribution samples, and 9 forecast samples.
- [ ] Apply AI-assisted initial review under `reviewer-user-01`; trigger an independent second reviewer for every risk condition and an independent adjudicator for disagreements.
- [ ] Validate all 18 public samples for leakage and all calculations for replayability.
- [ ] Set pilot status ready only when all nine dossier reviews are complete; otherwise preserve explicit rejection records and keep `formal_ready=false`.

Pilot assertions:

```python
assert dossier_count == 9
assert attribution_sample_count == 9
assert forecast_sample_count == 9
assert incomplete_review_count == 0
assert public_hidden_field_count == 0
```

### Task 4: Research and select companies for the remaining seven events

**Files:**
- Create: `outputs/fingoose_macro_event_company_v1/candidate_company_registry.jsonl`
- Extend: `configs/fingoose_macro_event_companies_v1.json`
- Add only archived files under: `inputs/fingoose_macro_event_company_v1/`

- [ ] Create a scored A-share candidate registry for event-03, event-04, event-06, event-07, event-08, event-09, and event-10.
- [ ] Score event/industry evidence, explicit business exposure, two official company result periods, counterevidence, archived source quality, and price-series replayability.
- [ ] Select exactly three companies per event only when every evidence gate passes; otherwise emit rejection reasons and block formal publication.
- [ ] Independently review candidate selection for unsupported causal wording and manufactured direction balance.

### Task 5: Build and audit the full 30-dossier release

**Files:**
- Modify: `configs/fingoose_macro_event_companies_v1.json`
- Modify: `configs/fingoose_macro_event_company_reviews_v1.jsonl`
- Generate only: `outputs/fingoose_macro_event_company_v1/`

- [ ] Build 10 events, 30 dossiers, 30 attribution samples, and 30 forecast samples.
- [ ] Complete dossier-level initial, triggered second, and disagreement adjudication reviews with independent identities.
- [ ] Enforce `WEAK_RELATION + UNSUPPORTED >= 25%`, `UP >= 15%`, `DOWN >= 15%`, and maximum association-label share `<= 60%` without altering evidence-led labels.
- [ ] Replay every number, verify every source snapshot/hash/locator, and reject rather than fill missing evidence.
- [ ] Mark `formal_ready=true` only with zero incomplete reviews, zero publication rejections, zero leakage findings, and passing label gates.

### Task 6: Extend the dashboard repository and read-only API

**Files:**
- Modify: `fingoose_macro_event_dashboard_v1.py`
- Modify: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Modify: `docs/superpowers/specs/2026-07-28-macro-event-dashboard-design.md`

- [ ] Write failing repository tests that load separate market and company roots and join four market samples plus three company dossiers under one event.
- [ ] Implement company indexes and overview distributions without weakening the existing market artifact checks.
- [ ] Write failing API tests for company dossier, company sample, company review, and combined event routes.
- [ ] Implement read-only endpoints and maintain strict public/internal audit separation.
- [ ] Run all dashboard repository/API tests against both real output roots.

### Task 7: Build and visually verify the unified dashboard

**Files:**
- Modify: `fingoose_macro_event_dashboard_v1.py`
- Modify: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Create: `work/macro_event_dashboard_v1/desktop.png`
- Create: `work/macro_event_dashboard_v1/mobile.png`
- Create: `work/macro_event_dashboard_v1/visual_validation.json`

- [ ] Write failing page-contract tests for `数据集概览`, `市场归因`, `公司影响`, and `审核记录`.
- [ ] Implement event detail with four market tasks and three company dossiers; implement company detail with exposure, operating/financial metrics, stock windows, transmission chain, counterevidence, forecast result, and review history.
- [ ] Add loading, empty, unavailable, and rejected states; ensure internal hidden labels never enter public training views.
- [ ] Run focused tests and the full Python suite with project-local `TEMP`/`TMP`.
- [ ] Start the local server and use Playwright at `1440x1000` and `390x844` to verify non-empty charts, no horizontal overflow, event switching, and company-detail interaction.
- [ ] Request final independent specification and code-quality reviews, fix all critical/important findings, and rerun complete verification before reporting readiness.

### Release Invariants

- [ ] `outputs/fingoose_macro_event_attribution_v1` remains byte-for-byte unchanged.
- [ ] `outputs/fingoose_formal_v1_macro` remains byte-for-byte unchanged.
- [ ] No source or output is written outside `D:/桌面/workspace/codex1`.
- [ ] Association language remains evidence-weighted post-event attribution, never strict causal proof.
- [ ] Missing evidence produces rejection or `formal_ready=false`, never fabricated records.
