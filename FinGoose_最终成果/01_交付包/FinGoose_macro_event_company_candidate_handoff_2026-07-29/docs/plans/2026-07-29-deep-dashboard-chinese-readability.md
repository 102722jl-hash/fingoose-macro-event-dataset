# FinGoose Deep Dashboard Chinese Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all four dashboard views readable in Chinese while preserving original evidence and links.

**Architecture:** Keep archived JSON immutable and add deterministic localization plus structured rendering in the independent JavaScript client. Use CSS components for summaries, source links, prediction emphasis, company facts, and review explanations.

**Tech Stack:** Native JavaScript, CSS, Python unittest, Playwright with Microsoft Edge.

---

### Task 1: Chinese display contract

**Files:**
- Modify: `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.js`

- [ ] Add failing page-asset tests for translation, original-link, prediction, company-summary and review-summary contracts.
- [ ] Run the focused unittest and confirm the new assertions fail.
- [ ] Add deterministic Chinese translations for all archived event titles, reasoning statements, source titles, gap reasons, review tokens and common financial fields.
- [ ] Run the focused unittest and confirm it passes.

### Task 2: Structured market and company rendering

**Files:**
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.js`
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.css`

- [ ] Replace overview English event/blocker text with Chinese summary cards.
- [ ] Render each market step as Chinese conclusion, evidence and original link instead of JSON-first output.
- [ ] Render a prominent short-term prediction panel with direction, horizon, confidence and invalidation conditions.
- [ ] Replace company stock, attribution and forecast JSON blocks with readable Chinese facts and explicit evidence gaps.
- [ ] Keep complete raw records in collapsible original-record sections.

### Task 3: Intuitive review records and verification

**Files:**
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.js`
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.css`

- [ ] Render market and company review summaries with translated status, label, confidence, triggers and core dimensions.
- [ ] Run Python and JavaScript static tests.
- [ ] Verify event-02 in desktop Edge: Chinese event summary, six market steps, prediction panel, seven company nodes, original source link, and translated review card.
- [ ] Confirm the HTTP service remains read-only and `formal_ready=false`.
