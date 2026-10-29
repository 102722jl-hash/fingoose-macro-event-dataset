# MySQL Company Enhancement Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an isolated MySQL-backed candidate bundle for company-industry mapping, analyst-rating windows, and pre-event financial baselines.

**Architecture:** A focused Python module invokes the local MySQL CLI through an injected query runner, normalizes vendor rows, enforces event cutoffs, validates records, and writes an independent candidate directory. Unit tests use fixture query results and never require a live database; one explicit integration command generates the real bundle through the read-only login path.

**Tech Stack:** Python 3.12 standard library, MySQL 8 CLI, JSON/JSONL, `unittest`.

---

### Task 1: Define failing contract tests

**Files:**
- Create: `tests/test_fingoose_mysql_company_enhancement_v1.py`

- [ ] **Step 1: Write fixture tests for deterministic anchors and industry membership**

```python
def test_builds_thirty_isolated_candidates(self):
    summary = build_mysql_company_enhancement(..., query_runner=fixture_runner)
    self.assertEqual(summary["company_candidate_count"], 30)
    self.assertFalse(summary["formal_ready"])
```

- [ ] **Step 2: Write tests for rating deduplication and explicit missing windows**

```python
def test_rating_payloads_are_deduplicated_without_hiding_same_day_variants(self):
    records = summarize_rating_rows(fixture_rows, anchor_date="2022-02-24")
    self.assertEqual(records["duplicate_row_count"], 1)
    self.assertEqual(records["distinct_observation_count"], 2)
```

- [ ] **Step 3: Write tests for pre-event financial cutoff**

```python
def test_financial_baseline_rejects_post_event_announcements(self):
    result = select_financial_baseline(rows, cutoff_date="2024-09-24")
    self.assertTrue(all(item["effective_announcement_date"] <= "2024-09-24" for item in result.values()))
```

- [ ] **Step 4: Run tests and verify RED**

Run: `python -m unittest tests.test_fingoose_mysql_company_enhancement_v1 -v`

Expected: import failure for `fingoose_mysql_company_enhancement_v1`.

### Task 2: Implement normalization and query boundaries

**Files:**
- Create: `code/fingoose_mysql_company_enhancement_v1.py`
- Create: `code/build_fingoose_mysql_company_enhancement_v1.py`

- [ ] **Step 1: Implement JSONL readers, stable IDs, anchor selection, and numeric/date normalization**
- [ ] **Step 2: Implement a MySQL CLI runner using an argument list and `--login-path`**
- [ ] **Step 3: Reject write statements and credential-bearing output configuration**
- [ ] **Step 4: Run focused tests and verify normalization tests pass**

Run: `python -m unittest tests.test_fingoose_mysql_company_enhancement_v1 -v`

Expected: normalization and security tests pass; output tests may still fail.

### Task 3: Implement the three candidate products

**Files:**
- Modify: `code/fingoose_mysql_company_enhancement_v1.py`

- [ ] **Step 1: Query all `fr_*_history` tables and build zero/one/many industry memberships**
- [ ] **Step 2: Query rating rows only for the 30 configured companies and each event's -60/+60 calendar-day window**
- [ ] **Step 3: Deduplicate identical rating payloads and retain distinct same-day variants**
- [ ] **Step 4: Query financial rows and retain only records announced on or before the event anchor**
- [ ] **Step 5: Emit explicit missing records rather than dropping companies**
- [ ] **Step 6: Run all focused tests and verify GREEN**

Run: `python -m unittest tests.test_fingoose_mysql_company_enhancement_v1 -v`

Expected: all tests pass.

### Task 4: Build validation, manifest, and documentation

**Files:**
- Modify: `code/fingoose_mysql_company_enhancement_v1.py`

- [ ] **Step 1: Validate counts, unique IDs, cutoff leakage, vendor status, and protected output isolation**
- [ ] **Step 2: Write summary, source manifest, validation report, SHA manifest, and README**
- [ ] **Step 3: Add tests that recompute hashes and assert `formal_ready=false`**
- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_fingoose_mysql_company_enhancement_v1 -v`

Expected: all tests pass and no production path is written.

### Task 5: Generate and verify the live candidate bundle

**Files:**
- Create: `work/mysql_company_enhancement_v1_candidate/*`

- [ ] **Step 1: Generate through the read-only login path**

Run:

```powershell
$env:PYTHONPATH='code'
python code/build_fingoose_mysql_company_enhancement_v1.py --root . --login-path fingoose-codex --database workspace
```

Expected: 30 impact candidates, 30 rating windows, 30 financial baseline records, `formal_ready=false`.

- [ ] **Step 2: Re-run the focused and existing company regression tests**

Run:

```powershell
python -m unittest tests.test_fingoose_mysql_company_enhancement_v1 tests.test_fingoose_macro_event_company_vendor_enhancement_v1 -v
```

Expected: all tests pass.

- [ ] **Step 3: Confirm production/UI fingerprints and Git state are unchanged**

Because this handoff directory is not a Git repository, compare explicit protected-file SHA-256 values captured before and after generation. Expected: all protected hashes unchanged.

