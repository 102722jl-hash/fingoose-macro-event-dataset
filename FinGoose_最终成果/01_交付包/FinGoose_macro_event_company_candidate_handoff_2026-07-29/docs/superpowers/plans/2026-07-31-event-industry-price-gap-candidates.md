# Event Industry, Price Window, and Timeline Gap Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce three isolated, reproducible candidate bundles for event-industry-company impacts, 30 A-share price windows, and eight timeline evidence gaps.

**Architecture:** Three focused Python modules consume immutable JSONL inputs and emit independent candidate bundles. The public price adapter accepts injected payloads for deterministic tests and performs network reads only in the CLI builder; the other two builders are local joins/audits.

**Tech Stack:** Python 3.12 standard library, `unittest`, JSON/JSONL, urllib, SHA-256.

---

### Task 1: Public Price Window Adapter

**Files:**
- Create: `tests/test_fingoose_public_company_price_windows_v1.py`
- Create: `code/fingoose_public_company_price_windows_v1.py`
- Create: `code/build_fingoose_public_company_price_windows_v1.py`

- [x] Write failing tests for ticker mapping, Eastmoney parsing, T0/T-1/D1/D3/D5/D20 selection, missing observations, and release boundaries.
- [x] Run the focused test and confirm failures are caused by the missing module.
- [x] Implement the minimal adapter, window calculator, bundle validator, and manifest writer.
- [x] Run the focused test to green.
- [x] Fetch all 30 event-company pairs into `work/company_price_windows_public_vendor_v1_candidate/` and preserve normalized snapshots plus SHA-256 values.

### Task 2: Event-Industry-Company Candidate Join

**Files:**
- Create: `tests/test_fingoose_event_industry_impact_v1.py`
- Create: `code/fingoose_event_industry_impact_v1.py`
- Create: `code/build_fingoose_event_industry_impact_v1.py`

- [x] Write failing tests for anchor-to-graph-to-company joins, conditional direction inheritance, observation-only anchors, and causal boundary fields.
- [x] Run the focused test and confirm the expected missing-module failure.
- [x] Implement the minimal deterministic join and bundle writer.
- [x] Run the focused test to green.
- [x] Generate `work/event_industry_impact_v1_candidate/` from the fixed 24 anchors and existing 30-company MySQL candidates.

### Task 3: Eight-Node Timeline Gap Audit

**Files:**
- Create: `tests/test_fingoose_timeline_gap_resolution_v1.py`
- Create: `code/fingoose_timeline_gap_resolution_v1.py`
- Create: `code/build_fingoose_timeline_gap_resolution_v1.py`

- [x] Write failing tests for exact eight-node selection, snapshot hash checks, double-time completeness, semantic mismatch, and non-promotable pending records.
- [x] Run the focused test and confirm the expected missing-module failure.
- [x] Implement a read-only local audit that never changes source timeline records.
- [x] Run the focused test to green.
- [x] Generate `work/timeline_gap_resolution_v1_candidate/`, preserving honest blockers when independent evidence is insufficient.

### Task 4: Integrated Verification

**Files:**
- Verify: all files created above
- Verify: production v2 baseline files

- [x] Run all three focused suites and relevant existing regression suites.
- [x] Parse every JSON/JSONL output and recompute every manifest hash.
- [x] Confirm the protected production SHA-256 triplet is unchanged.
- [x] Report candidate counts, missing observations, newly closable gaps, remaining blockers, and formal-release boundaries.
