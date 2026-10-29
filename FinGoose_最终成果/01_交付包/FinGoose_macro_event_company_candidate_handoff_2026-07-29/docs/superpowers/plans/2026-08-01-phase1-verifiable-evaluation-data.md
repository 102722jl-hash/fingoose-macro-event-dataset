# FinGoose Phase 1 Verifiable Evaluation Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an isolated `CANDIDATE` package that closes the 50-node evidence baseline, reviews 111 dynamic bindings, upgrades industry/company windows, and enforces three independent evaluation gates.

**Architecture:** Treat the four existing candidate directories as read-only inputs. A Python package under `work/verifiable_evaluation_phase1_v2_candidate/src/` normalizes evidence, derives downstream projections, and validates release gates; generated JSONL/JSON reports are written only under the new candidate directory. Each transformation records provenance and refuses unsupported precision, semantic rewrites without audit records, causal labels from observation-only anchors, or `CONFIRMED` AI output.

**Tech Stack:** Python 3 standard library, `unittest`, JSON/JSONL, official web snapshots, read-only MySQL query manifests.

---

### Task 1: Establish isolated package and evidence contract

**Files:**
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/io_utils.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/evidence.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/tests/test_evidence.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/README.md`

- [ ] **Step 1: Write failing tests for JSONL parsing and the 50/0 evidence contract**

```python
def test_date_precision_accepts_date_but_rejects_invented_midnight():
    record = verified_record(occurred_at="2025-01-20", occurred_at_precision="DATE")
    assert validate_verified_node(record) == []
    record["occurred_at"] = "2025-01-20T00:00:00Z"
    assert "unsupported occurred_at precision" in validate_verified_node(record)

def test_semantic_change_requires_audit_and_downstream_impact():
    record = verified_record(semantic_change=True, replacement_audit=None)
    assert "missing replacement audit" in validate_verified_node(record)
```

- [ ] **Step 2: Run the evidence tests and verify RED**

Run: `python -m unittest discover -s work/verifiable_evaluation_phase1_v2_candidate/tests -p "test_evidence.py" -v`

Expected: FAIL because `src.evidence` does not exist.

- [ ] **Step 3: Implement minimal evidence validation**

Implement `read_jsonl`, `write_jsonl`, `validate_verified_node`, date-versus-datetime precision checks, non-empty source/quote/locator requirements, and semantic replacement audit requirements. A `DATE` value must match `YYYY-MM-DD`; a timestamp precision must include a timezone and explicit locator evidence.

- [ ] **Step 4: Run evidence tests and verify GREEN**

Run the Step 2 command. Expected: all evidence tests PASS.

- [ ] **Step 5: Record immutable input paths and candidate-only output policy in README**

List the four read-only inputs, the new output path, `formal_ready=false`, `SHA_GATE=DEFERRED`, and the prohibition on generated `CONFIRMED` states.

### Task 2: Close the eight timeline gaps and rebuild promotions

**Files:**
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/timeline.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/config/evidence_resolutions.json`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/tests/test_timeline.py`
- Create: generated `timeline_nodes.jsonl`, `source_manifest.jsonl`, `semantic_replacements.jsonl`, `promotable_milestones.jsonl`, `timeline_validation_report.json`

- [ ] **Step 1: Write failing tests for all eight explicit resolutions**

Tests must assert: 50 unique stable node IDs; zero pending nodes; both times and precisions are non-empty; all verified nodes contain quote and locator provenance; `fast-event-02-M01` has `semantic_change=true` and a downstream-impact audit; date-only official pages remain `DATE`; promotion is recomputed and never copied from the old 18-row file.

- [ ] **Step 2: Run timeline tests and verify RED**

Run: `python -m unittest work.verifiable_evaluation_phase1_v2_candidate.tests.test_timeline -v`

Expected: FAIL because the timeline builder and resolution file do not exist.

- [ ] **Step 3: Inventory local official snapshots before network retrieval**

Resolve candidate manifest records and snapshot bodies for `02-M01`, `05-M01`, `05-M04`, `06-M01`, `07-M05`, `10-M01`, `10-M04`, and `10-M05`. Record source tier, official URL, quote, locator, occurrence evidence, publication evidence, and precision. Do not infer a publication time from the node's claimed time.

- [ ] **Step 4: Retrieve only missing official evidence**

Search official domains and extract the relevant official page or document. If the source proves only a date, store `YYYY-MM-DD` with precision `DATE`; do not normalize it to midnight. Store retrieval metadata and a local snapshot when licensing permits.

- [ ] **Step 5: Implement timeline overlay and promotion derivation**

The builder copies 42 input nodes, overlays the eight audited resolutions, validates all 50 records, then calculates promotion eligibility from current fields: verified evidence, complete dual-time locators, no gap, no target collision, no cross-event source, valid expectation policy, and completed downstream review for semantic changes.

- [ ] **Step 6: Run timeline tests and verify GREEN**

Run the Step 2 command plus `python work/verifiable_evaluation_phase1_v2_candidate/src/timeline.py --build`. Expected report: `node_count=50`, `verified_count=50`, `pending_evidence_count=0`, `hard_failures=[]`.

### Task 3: Review anchors and 111 dynamic bindings

**Files:**
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/bindings.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/tests/test_bindings.py`
- Create: generated `anchor_catalog.jsonl`, `dynamic_edge_bindings.jsonl`, `counterevidence_dispositions.jsonl`, `binding_validation_report.json`

- [ ] **Step 1: Write failing tests for review-state and causality boundaries**

Tests must reject `CONFIRMED`, reject `PROPOSED` in final output, require immediate/short/medium directions and min/max lag, require conditions/invalidation/evidence/review, prevent `OBSERVATION_ONLY` anchors from causal attribution, close all 39 unlinked counterevidence items by link or documented `NOT_APPLICABLE`, and close the one pinned-anchor status mismatch.

- [ ] **Step 2: Run binding tests and verify RED**

Run: `python -m unittest work.verifiable_evaluation_phase1_v2_candidate.tests.test_bindings -v`

Expected: FAIL because `src.bindings` does not exist.

- [ ] **Step 3: Implement deterministic binding review rules**

Use `AI_REVIEWED` only when every required field and evidence boundary passes. Use `REJECTED` for semantic/directional contradictions. Use `NEEDS_HUMAN_REVIEW` for research judgments not decidable from the package. Keep event-fact evidence separate from mechanism evidence and attach a Chinese review rationale with timestamp and reviewer type `AI_DESK_REVIEW`.

- [ ] **Step 4: Reproject anchors from the 50/0 baseline and review 111 bindings**

Preserve stable binding IDs where semantics are unchanged. Recompute any binding affected by the `02-M01` replacement. Produce a disposition row for every previously unlinked counterevidence item.

- [ ] **Step 5: Run binding tests and verify GREEN**

Expected: 24 anchors, 111 bindings, zero `PROPOSED`, zero `CONFIRMED`, zero unresolved counterevidence, zero anchor-status conflicts, and no hard failures.

### Task 4: Upgrade industry and company market layers

**Files:**
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/market.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/tests/test_market.py`
- Create: generated `event_industry_impacts.jsonl`, `company_price_windows.jsonl`, `company_exposure_gaps.jsonl`, `mysql_query_manifest.jsonl`, `market_validation_report.json`

- [ ] **Step 1: Write failing tests for stable lineage and reproducible returns**

Tests must require event node to anchor to binding to channel/intermediate variable to SW1/SW2 industry to company lineage; assert 43 industry rows and 72 company links parse; preserve unsupported directions as `NEEDS_HUMAN_REVIEW`; require T-20/T-1/T0/D1/D3/D5/D20; recompute absolute, broad-market-relative, and industry-relative returns; require trading-calendar and suspension alignment plus confounding grade.

- [ ] **Step 2: Run market tests and verify RED**

Run: `python -m unittest work.verifiable_evaluation_phase1_v2_candidate.tests.test_market -v`

Expected: FAIL because `src.market` does not exist.

- [ ] **Step 3: Implement industry lineage projection without hindsight direction selection**

Map current records to reviewed bindings. Fill directions only from mechanism evidence; otherwise mark `NEEDS_HUMAN_REVIEW`. Record index/ETF proxies explicitly and do not use post-event prices to choose direction.

- [ ] **Step 4: Enrich the 30 company windows from existing public-vendor inputs and read-only data**

Add missing T-20 observations, broad-market and industry benchmark observations where available, relative-return formulas, session alignment, source/provider/licence fields, and exposure evidence gaps. Every database use must log database/table, selected fields, filters, time range, and row count in `mysql_query_manifest.jsonl`.

- [ ] **Step 5: Run market tests and verify GREEN**

Expected: 43 industry rows, 72 company links, 30 company windows, all required observation keys, reproducible return formulas, and no hindsight-filled direction.

### Task 5: Build three-track benchmark and release gates

**Files:**
- Create: `work/verifiable_evaluation_phase1_v2_candidate/src/gates.py`
- Create: `work/verifiable_evaluation_phase1_v2_candidate/tests/test_gates.py`
- Create: generated `benchmark_cases.jsonl`, `hidden/benchmark_labels.jsonl`, `evaluation_report.json`, `manifest.json`, `validation_report.json`

- [ ] **Step 1: Write failing tests for event-level isolation and hard failures**

Tests must verify three separate tracks with no composite score, event-level public/hidden separation, D3 cutoff isolation, refusal scoring, exclusion of `MATERIAL`/`DOMINANT` confounds from clean attribution, no causal labels from observation anchors, and hard failures for fabricated sources, cross-event citations, non-recomputable values, leakage, or forbidden review states.

- [ ] **Step 2: Run gate tests and verify RED**

Run: `python -m unittest work.verifiable_evaluation_phase1_v2_candidate.tests.test_gates -v`

Expected: FAIL because `src.gates` does not exist.

- [ ] **Step 3: Implement benchmark projection and gate validator**

Generate public cases and hidden labels into separate paths. Keep timeline reconstruction, graph construction, and direction/refusal scores independent. The manifest records schemas, counts, source scope, deferred SHA status, known gaps, and vendor licence boundary.

- [ ] **Step 4: Run the full build and test suite**

Run: `python -m unittest discover -s work/verifiable_evaluation_phase1_v2_candidate/tests -v`

Run: `python work/verifiable_evaluation_phase1_v2_candidate/src/gates.py --build-all`

Expected: all tests PASS; `hard_failures=[]`; `formal_ready=false`; `sha_gate=DEFERRED`; no current UI or production input file modified.

- [ ] **Step 5: Produce reconciliation and limitations report**

Document the input 42/8 baseline, final evidence counts, old-versus-new promotion differences, all semantic replacements, binding status totals, unresolved human-review items, market coverage, database queries, vendor-licence restrictions, and why the candidate is not formally ready.

