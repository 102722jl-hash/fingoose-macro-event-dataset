# Task-specific Q&A Answers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evidence audit, market validation, and industry-company tabs answer their own questions, while making immediate, short-term, and medium-term reasoning materially distinct for all ten macro events.

**Architecture:** Add an additive reasoning implementation that derives a task-specific `task_answer` from the already-loaded official evidence, industry windows, and company dossiers. Add an additive UI implementation that dispatches on `task_type`, preserving the existing macro-event workbench and downstream sections.

**Tech Stack:** Python 3, JSON/JSONL artifacts, static HTML/CSS/JavaScript, pytest, Playwright.

---

### Task 1: Lock the contracts with failing tests

**Files:**
- Create: `tests/test_fingoose_qa_horizon_reasoning_v2.py`
- Test: `tests/test_fingoose_qa_task_specific_answers_v2.py`

- [ ] Assert the three `task_answer` schemas and three task-specific UI renderer names.
- [ ] Assert all ten events expose distinct immediate (`T0/D1`), short-term (`D3/D5`), and medium-term (`D20`) reasoning.
- [ ] Run `python -m pytest -q tests\test_fingoose_qa_task_specific_answers_v2.py tests\test_fingoose_qa_horizon_reasoning_v2.py` and confirm expected missing-field failures.

### Task 2: Generate task-specific answer data

**Files:**
- Create: `code/fingoose_qa_reasoning_v2_impl_003.py`

- [ ] Wrap `fingoose_qa_reasoning_v2_impl_002.build_qa_records` and load the existing company-impact UI bundle once.
- [ ] Build evidence-audit facts/inferences/calculations/refusals.
- [ ] Build market-validation six-window results and three horizon verdicts from relative returns.
- [ ] Build industry-company results from three company dossiers, pre-event disclosures, mechanisms, directions, conditions, counterevidence, confounders, and trading status.
- [ ] Add distinct `horizon_reasoning_zh` objects using different variables and windows for each horizon.
- [ ] Run focused pytest and confirm the data-contract tests pass.

### Task 3: Render each tab as a distinct answer

**Files:**
- Create: `code/fingoose_company_impact_qa_ui_v2_impl_005.py`

- [ ] Add `qaEvidenceAuditAnswer`, `qaMarketValidationAnswer`, and `qaIndustryCompanyAnswer`.
- [ ] Override `qaSection` to dispatch by `task_type` while keeping the existing page sections.
- [ ] Render horizon reasoning with separate observation focus, window basis, and conclusion text.
- [ ] Run focused pytest and confirm all task and UI assertions pass.

### Task 4: Rebuild and verify artifacts

**Files:**
- Regenerate: `work/qa_reasoning_pilot_v2_candidate/*`
- Regenerate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Regenerate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [ ] Run the Q&A candidate and combined UI builders.
- [ ] Run focused and full Python regression tests.
- [ ] Run desktop/mobile browser checks across all ten events and all three specialized tabs.
- [ ] Confirm review-state fields and public/private boundaries remain unchanged.
