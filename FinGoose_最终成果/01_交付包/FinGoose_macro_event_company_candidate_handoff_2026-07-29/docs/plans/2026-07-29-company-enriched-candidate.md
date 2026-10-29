# FinGoose Company Enriched Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate every candidate company dossier with non-causal identity metadata and integrate all already archived, auditable event-02 company evidence into a separate enriched candidate release and unified dashboard.

**Architecture:** Rebuild the unchanged candidate dataset into a new output root, then deterministically merge the isolated historical evidence package by company and event. Keep post-cutoff facts out of public forecast projections, preserve unresolved fields as explicit evidence gaps, and have the dashboard distinguish pending assessment from unsupported attribution.

**Tech Stack:** Python 3 standard library, unittest, JSON/JSONL, native HTML/CSS/JavaScript.

---

### Task 1: Enrichment contract

**Files:**
- Create: `tests/test_fingoose_macro_event_company_enriched_candidate_v1.py`
- Create: `build_fingoose_macro_event_company_enriched_candidate_v1.py`

- [ ] Write failing tests for 30 populated identity records, event-02 source/fact integration, leakage isolation, and protected-root preservation.
- [ ] Run the focused test and confirm it fails because the enrichment builder does not exist.
- [ ] Implement deterministic enrichment and validation.
- [ ] Run the focused test and confirm it passes.

### Task 2: Dashboard semantics and detail

**Files:**
- Modify: `fingoose_macro_event_dashboard_v1.py`
- Modify: `fingoose_macro_event_dashboard_v1.html`
- Modify: `tests/test_fingoose_macro_event_company_enriched_candidate_v1.py`

- [ ] Add failing tests that pending dossiers are shown as unassessed and event-02 detail exposes values, units, and sources.
- [ ] Implement enriched-root defaulting and explicit pending-assessment UI labels.
- [ ] Expand market and company cards to show their available windows, values, units, evidence and gaps.
- [ ] Run focused and existing dashboard tests.

### Task 3: Build and verify

**Files:**
- Generate only: `outputs/fingoose_macro_event_company_enriched_candidate_v1/`

- [ ] Build the enriched candidate output.
- [ ] Verify counts, hashes, leakage checks, and `formal_ready=false`.
- [ ] Start the dashboard and smoke-test API responses.
