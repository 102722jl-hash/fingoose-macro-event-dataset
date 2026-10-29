# FinGoose Company Confounder Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the confounder, counterevidence, and trading-status evidence gaps for all 30 frozen event-company mappings and replace generic unresolved UI placeholders with evidence-backed Chinese research arguments.

**Architecture:** Preserve the 455-title CNINFO snapshots as immutable intake, add five review ledgers keyed by `mapping_id`, and derive the aggregate `company_confounders.jsonl` only after strict completeness gates. Network retrieval and PDF extraction remain separate from review judgments so failed downloads stay reproducible and unresolved instead of becoming inferred facts.

**Tech Stack:** Python 3, JSONL, `urllib.request`, `pypdf`/`pdfplumber`, unittest/pytest, static HTML/CSS/JavaScript, Playwright with installed Chrome.

---

### Task 1: Define evidence-closure schemas and grade gates

**Files:**
- Create: `code/fingoose_company_confounder_evidence_closure_v2.py`
- Create: `tests/test_fingoose_company_confounder_evidence_closure_v2.py`

- [ ] **Step 1: Write failing tests for review validation and grade eligibility**

```python
def test_clean_requires_complete_search_body_reviews_and_trading():
    from fingoose_company_confounder_evidence_closure_v2 import derive_grade

    complete = {
        "search_status": "COMPLETE",
        "candidate_count": 0,
        "body_reviewed_count": 0,
        "unresolved_reasons": [],
    }
    trading = {"overall_status": "VERIFIED_TRADING"}
    assert derive_grade(complete, [], trading, []) == "CLEAN"
    assert derive_grade(dict(complete, search_status="INCOMPLETE"), [], trading, []) == "UNRESOLVED"
    assert derive_grade(complete, [], {"overall_status": "UNRESOLVED"}, []) == "UNRESOLVED"


def test_title_only_candidate_cannot_receive_resolved_grade():
    from fingoose_company_confounder_evidence_closure_v2 import derive_grade

    audit = {
        "search_status": "INCOMPLETE",
        "candidate_count": 1,
        "body_reviewed_count": 0,
        "unresolved_reasons": ["BODY_REVIEW_INCOMPLETE"],
    }
    candidate = {"body_review_status": "TITLE_ONLY", "severity_candidate": "MATERIAL"}
    assert derive_grade(audit, [candidate], {"overall_status": "VERIFIED_TRADING"}, []) == "UNRESOLVED"
```

- [ ] **Step 2: Run the new test module and verify RED**

Run:

```powershell
python -m pytest tests\test_fingoose_company_confounder_evidence_closure_v2.py -q
```

Expected: import failure for `fingoose_company_confounder_evidence_closure_v2`.

- [ ] **Step 3: Implement validators and deterministic grade derivation**

The module must expose:

```python
VALID_RELEVANCE = {"RELEVANT", "MINOR_RELEVANCE", "IRRELEVANT", "UNRESOLVED"}
VALID_GRADES = {"CLEAN", "MINOR", "MATERIAL", "DOMINANT", "UNRESOLVED"}


def validate_body_review(row: Mapping[str, Any]) -> list[str]: ...
def validate_search_audit(row: Mapping[str, Any]) -> list[str]: ...
def validate_trading_review(row: Mapping[str, Any]) -> list[str]: ...
def validate_counterevidence_review(row: Mapping[str, Any]) -> list[str]: ...


def derive_grade(search_audit, body_reviews, trading_review, counterevidence):
    if search_audit.get("search_status") != "COMPLETE":
        return "UNRESOLVED"
    if search_audit.get("candidate_count") != search_audit.get("body_reviewed_count"):
        return "UNRESOLVED"
    if trading_review.get("overall_status") not in {"VERIFIED_TRADING", "VERIFIED_SUSPENDED"}:
        return "UNRESOLVED"
    if any(row.get("relevance_decision") == "UNRESOLVED" for row in body_reviews):
        return "UNRESOLVED"
    severities = [
        row["severity_candidate"]
        for row in body_reviews
        if row.get("relevance_decision") in {"RELEVANT", "MINOR_RELEVANCE"}
    ]
    if "DOMINANT" in severities:
        return "DOMINANT"
    if "MATERIAL" in severities:
        return "MATERIAL"
    if severities:
        return "MINOR"
    return "CLEAN"
```

Validation must require official URL, first-public time, body locator, verbatim quote and affected windows for every resolved relevant candidate.

- [ ] **Step 4: Run the tests and verify GREEN**

Expected: all tests in the new module pass.

### Task 2: Build the official announcement-body retrieval layer

**Files:**
- Create: `code/fetch_fingoose_company_announcement_bodies_v2.py`
- Create: `tests/test_fetch_fingoose_company_announcement_bodies_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/sources/company_announcements/pdf/*.pdf`
- Generate: `work/company_impact_high_quality_v2_candidate/sources/company_announcements/text/*.txt`
- Generate: `work/company_impact_high_quality_v2_candidate/announcement_body_retrieval.jsonl`

- [ ] **Step 1: Write failing tests for URL normalization, job coverage and failure records**

```python
def test_build_jobs_covers_all_registered_title_candidates():
    jobs = build_download_jobs(confounder_candidates)
    assert len(jobs) == 47
    assert len({job["announcement_id"] for job in jobs}) == 47
    assert all(job["source_url"].startswith("https://static.cninfo.com.cn/") for job in jobs)


def test_failed_download_is_a_persisted_unresolved_record():
    record = retrieval_failure(job, "HTTP_404")
    assert record["retrieval_status"] == "FAILED"
    assert record["body_review_eligible"] is False
    assert record["failure_reason"] == "HTTP_404"
```

- [ ] **Step 2: Verify RED for the missing retrieval module**

Run the focused test and confirm the module import fails.

- [ ] **Step 3: Implement reproducible download jobs and PDF text extraction**

The script must:

1. Read `configs/company_impact_high_quality_v2/confounders.jsonl`.
2. Normalize the official `source_url` and extract `announcement_id`.
3. Refuse non-CNINFO, non-SSE and non-SZSE hosts.
4. Download to an explicit per-announcement path with bounded timeout and retry count.
5. Extract text with `pypdf`; use `pdfplumber` only when the first extraction is empty.
6. Save one retrieval row with `RETRIEVED / FAILED / TEXT_EMPTY` and the exact failure reason.
7. Never mark a failed or empty record as body-reviewed.

- [ ] **Step 4: Run the 47-document retrieval batch**

Run:

```powershell
python code\fetch_fingoose_company_announcement_bodies_v2.py --root . --candidate-root work\company_impact_high_quality_v2_candidate
```

Expected: 47 retrieval rows; each row has either a readable official snapshot and extracted text or an explicit failure.

- [ ] **Step 5: Re-run retrieval tests and verify GREEN**

### Task 3: Produce body-level announcement review records

**Files:**
- Create: `code/build_fingoose_announcement_body_reviews_v2.py`
- Create: `tests/test_build_fingoose_announcement_body_reviews_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/announcement_body_reviews.jsonl`

- [ ] **Step 1: Write failing tests for quote, locator and disposition coverage**

```python
def test_each_retrieval_has_exactly_one_body_review():
    assert {row["announcement_id"] for row in reviews} == {
        row["announcement_id"] for row in retrievals
    }


def test_relevant_review_has_verbatim_quote_and_locator():
    for row in reviews:
        if row["relevance_decision"] in {"RELEVANT", "MINOR_RELEVANCE"}:
            assert row["original_quote"]
            assert row["body_locator"]
            assert row["original_quote"] in extracted_text[row["announcement_id"]]
            assert row["affected_windows"]
```

- [ ] **Step 2: Verify RED because the review builder and output do not exist**

- [ ] **Step 3: Implement candidate extraction and review-record validation**

The builder must create one record per retrieval. Retrieved documents receive a body-level disposition based on the actual text and event window. Failed retrievals receive:

```python
{
    "body_review_status": "UNRESOLVED_RETRIEVAL",
    "relevance_decision": "UNRESOLVED",
    "severity_candidate": "UNRESOLVED",
    "original_quote": None,
    "body_locator": None,
    "review_status": "NEEDS_HUMAN_REVIEW",
}
```

Resolved review records must distinguish capital return, financing, earnings, major contract/order, regulatory approval, restructuring, litigation and operating-event mechanisms. Generic English template mechanisms from the title-only intake must not be copied into the final Chinese argument.

- [ ] **Step 4: Run the body-review builder and inspect every non-irrelevant record**

Run:

```powershell
python code\build_fingoose_announcement_body_reviews_v2.py --root . --candidate-root work\company_impact_high_quality_v2_candidate
```

Expected: 47 body-review records, with every resolved quote present verbatim in its extracted official text.

- [ ] **Step 5: Run tests and verify GREEN**

### Task 4: Build complete title-search and negative-result audits

**Files:**
- Create: `code/build_fingoose_company_confounder_search_audits_v2.py`
- Create: `tests/test_build_fingoose_company_confounder_search_audits_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/company_confounder_search_audits.jsonl`

- [ ] **Step 1: Write failing tests for 30-mapping and 455-title coverage**

```python
def test_search_audits_cover_frozen_scope():
    assert len(audits) == 30
    assert len({row["mapping_id"] for row in audits}) == 30
    assert sum(row["title_count"] for row in audits) == 455


def test_complete_search_requires_all_candidate_bodies_disposed():
    for row in audits:
        if row["search_status"] == "COMPLETE":
            assert row["candidate_count"] == row["body_reviewed_count"]
            assert not row["unresolved_reasons"]
```

- [ ] **Step 2: Verify RED because the audit builder does not exist**

- [ ] **Step 3: Implement deterministic title classification and audit aggregation**

Use fixed query categories declared in the output: earnings/forecast, capital return/shareholding, financing/debt, contracts/orders, litigation/regulation, restructuring/assets, suspension/resumption and material operations. Each audit must list the 30 snapshot path, date window, title count, candidate IDs, rejected-title counts and reasons, body-review count, source provider and unresolved reasons.

For zero-candidate mappings, `negative_result_basis` must state that all titles in the captured official window were classified and no configured material category matched. It may become `COMPLETE` only when snapshot coverage and window bounds are present.

- [ ] **Step 4: Generate audits and verify the exact 30/455 coverage counts**

- [ ] **Step 5: Run tests and verify GREEN**

### Task 5: Verify trading status and build company-level counterevidence

**Files:**
- Create: `code/build_fingoose_company_trading_and_counterevidence_v2.py`
- Create: `tests/test_build_fingoose_company_trading_and_counterevidence_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/trading_status_reviews.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/company_counterevidence_reviews.jsonl`

- [ ] **Step 1: Write failing tests for six-window trading alignment and non-empty counterevidence disposition**

```python
def test_trading_reviews_cover_six_actual_dates():
    for row in trading_reviews:
        assert set(row["window_reviews"]) == {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
        for review in row["window_reviews"].values():
            assert review["actual_date"]
            assert review["status"] in {"VERIFIED_TRADING", "VERIFIED_SUSPENDED", "VERIFIED_RESUMED", "UNRESOLVED"}


def test_each_mapping_has_counterevidence_or_negative_search_record():
    assert {row["mapping_id"] for row in counterevidence_reviews} == mapping_ids
    assert all(row["findings"] or row["negative_search_basis"] for row in counterevidence_reviews)
```

- [ ] **Step 2: Verify RED for missing builders and ledgers**

- [ ] **Step 3: Implement trading verification from existing market lineage**

For each horizon, require an actual date, non-null company observation and the existing public-price source record before assigning `VERIFIED_TRADING`. A missing observation requires an official suspension/resumption notice before a suspension status is assigned; otherwise use `UNRESOLVED`.

- [ ] **Step 4: Build counterevidence from official company evidence and reviewed announcements**

Use the existing `LIMITATIONS_AND_COUNTEREVIDENCE` dossier evidence, relevant event-window announcements and direction invalidation conditions. Every finding must carry an existing evidence ID or reviewed announcement ID, verbatim quote, locator, source URL and affected horizon. If none is found, save the searched evidence categories and `negative_search_basis` rather than an empty list.

- [ ] **Step 5: Generate both 30-row ledgers and verify GREEN**

### Task 6: Derive aggregate confounder records and Chinese arguments

**Files:**
- Create: `code/build_fingoose_company_confounder_closure_v2.py`
- Create: `tests/test_build_fingoose_company_confounder_closure_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/company_confounder_arguments.jsonl`
- Regenerate: `work/company_impact_high_quality_v2_candidate/company_confounders.jsonl`

- [ ] **Step 1: Write failing tests for 30 arguments, grade gates and lineage**

```python
def test_arguments_are_research_readable_and_evidence_linked():
    assert len(arguments) == 30
    for row in arguments:
        assert 250 <= len(row["argument_zh"]) <= 600
        assert row["evidence_ids"] or row["negative_search_audit_id"]
        assert row["review_status"] == "NEEDS_HUMAN_REVIEW"


def test_clean_never_bypasses_completeness_gate():
    for row in confounders:
        if row["overall_grade"] == "CLEAN":
            assert row["company_confounder_status"] == "REVIEWED"
            assert row["suspension_status"] == "VERIFIED_TRADING"
            assert not row["unresolved_reasons"]
```

- [ ] **Step 2: Verify RED because closure outputs are absent**

- [ ] **Step 3: Implement aggregate record construction**

Join all five review ledgers by `mapping_id`, call the Task 1 grade function, set `score_eligibility`, and preserve all source IDs. `MATERIAL`, `DOMINANT` and `UNRESOLVED` remain `CHALLENGE_ONLY`. All aggregate records retain `formal_ready=false` and `causal_attribution_allowed=false`.

- [ ] **Step 4: Generate structured Chinese arguments**

Build each argument from fixed evidence-backed clauses in this order: event hypothesis, announcement findings, horizon interference, trading status, counterevidence, grade and refusal boundary. Do not insert a claim that is absent from the joined ledgers. Store section-level evidence IDs so each paragraph is traceable.

- [ ] **Step 5: Generate outputs and verify GREEN**

### Task 7: Integrate completion gates, package build and UI

**Files:**
- Modify: `code/build_fingoose_company_candidate_completion_v2.py`
- Modify: `code/build_fingoose_company_impact_high_quality_v2.py`
- Modify: `code/fingoose_company_candidate_completion_v2.py`
- Modify: `code/fingoose_company_impact_ui_v2.py`
- Modify: `tests/test_fingoose_company_candidate_completion_v2.py`
- Modify: `tests/test_build_fingoose_company_impact_high_quality_v2.py`
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Regenerate: `work/company_impact_high_quality_v2_candidate/candidate_completion_report.jsonl`
- Regenerate: `work/company_impact_high_quality_v2_candidate/validation_report.json`
- Regenerate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Regenerate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [ ] **Step 1: Write failing integration and UI tests**

Require the package to contain all five new ledgers, 30 aggregate arguments and exact mapping coverage. Require the UI to render `argument_zh`, body-review evidence links, affected windows, trading status and search-audit evidence. Assert the old sentence `公告标题检索未发现高风险候选，正文检索与公司级反证仍待完成` is absent.

- [ ] **Step 2: Verify RED against the current package and renderer**

- [ ] **Step 3: Integrate closure generation before completion evaluation**

Call `build_fingoose_company_confounder_closure_v2.build()` before `evaluate_completion()`. Extend candidate file copying and manifest generation to include all new outputs. Completion remains `OPEN` when the grade is `UNRESOLVED`, search is incomplete or trading is unresolved.

- [ ] **Step 4: Replace the generic UI placeholder with three explicit states**

Render:

1. `REVIEWED`: full Chinese argument, grade, window chips, evidence excerpts and official links.
2. `SEARCH_COMPLETE_NO_MATERIAL_CONFOUNDER`: negative-search scope and clean/minor basis.
3. `UNRESOLVED`: the exact missing body, trading or counterevidence items.

Keep technical IDs and search parameters in collapsed details. Do not show a blank confounder list.

- [ ] **Step 5: Rebuild the package and static UI**

Run:

```powershell
python code\build_fingoose_company_impact_high_quality_v2.py --root . --output work\company_impact_high_quality_v2_candidate
```

- [ ] **Step 6: Run focused integration tests and verify GREEN**

### Task 8: Run data, leakage and browser acceptance checks

**Files:**
- Modify only if verification exposes a defect.

- [ ] **Step 1: Run all confounder, completion, builder and UI tests**

```powershell
python -m pytest tests\test_fingoose_company_confounder_evidence_closure_v2.py tests\test_fetch_fingoose_company_announcement_bodies_v2.py tests\test_build_fingoose_announcement_body_reviews_v2.py tests\test_build_fingoose_company_confounder_search_audits_v2.py tests\test_build_fingoose_company_trading_and_counterevidence_v2.py tests\test_build_fingoose_company_confounder_closure_v2.py tests\test_fingoose_company_impact_confounders_v2.py tests\test_fingoose_company_candidate_completion_v2.py tests\test_build_fingoose_company_impact_high_quality_v2.py tests\test_fingoose_company_impact_ui_v2.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run a standalone coverage audit**

Assert:

```text
mapping_ids = 30
title_snapshots = 30
title_records = 455
body_review_records = 47
search_audits = 30
trading_reviews = 30
counterevidence_reviews = 30
arguments = 30
```

Also assert no `CLEAN` row violates completeness gates and no empty array is used as proof of completed negative research.

- [ ] **Step 3: Verify publication boundaries**

Search the candidate package for `formal_ready=true`, `sha_gate=ENFORCED`, hidden labels or confirmed AI judgments. Expected: no matches.

- [ ] **Step 4: Verify Chrome interactions and responsive layout**

At 1440px and 390px, visit all ten events and confirm each company displays one of the three explicit confounder states, argument text or precise unresolved blockers, official evidence links and affected windows. Verify no console errors, document-level horizontal overflow or text overlap.

- [ ] **Step 5: Record final counts and unresolved external failures**

Report retrieved, failed and empty PDFs separately; report grade counts and completion counts without treating unresolved external failures as clean evidence.

## Execution Notes

- This directory is not a Git repository, so commit steps are intentionally omitted. Do not initialize Git as part of this plan.
- Network retrieval requires explicit permission if the execution sandbox blocks official CNINFO/SSE/SZSE requests.
- Existing source snapshots and upstream event, market and transmission data remain unchanged.
- The plan closes candidate evidence and display gaps; it does not perform final human sign-off or SHA publication enforcement.
