# FinGoose Company Impact High-Quality v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a traceable 23-company master-dossier and 30 event-company evaluation dataset linked to the existing ten-event timeline, transmission graph, industry layer, reproducible price windows, relative returns, confounders, and one integrated Chinese UI.

**Architecture:** Keep `work/verifiable_evaluation_phase1_v2_candidate/` immutable and build a new package under `work/company_impact_high_quality_v2_candidate/`. Curated claim-level intake files feed small Python modules for lineage, evidence, direction, market calculations, confounders, gates, and UI projection. Every downstream record carries stable IDs back to the event anchor and every AI direction remains `NEEDS_HUMAN_REVIEW`.

**Tech Stack:** Python 3.12 standard library, JSON/JSONL, `unittest`, existing public-vendor adapters, read-only MySQL where available, HTML/CSS/vanilla JavaScript, browser screenshot QA.

**Repository note:** This handoff directory is not a Git repository. Commit steps are replaced by isolated-output checkpoints and validation reports; do not initialize Git or overwrite existing candidate packages.

---

## File Map

**Create:**

- `code/fingoose_company_impact_io_v2.py`: canonical JSON/JSONL I/O and stable IDs.
- `code/fingoose_company_impact_lineage_v2.py`: 23/30 registry and upstream linkage.
- `code/fingoose_company_impact_evidence_v2.py`: claim-level evidence and dossier gates.
- `code/fingoose_company_impact_direction_v2.py`: direction candidates and leakage rules.
- `code/fingoose_company_impact_market_v2.py`: T0 alignment, benchmark returns, suspension states.
- `code/fingoose_company_impact_confounders_v2.py`: confounder and counterevidence gates.
- `code/fingoose_company_impact_ui_v2.py`: unified UI data projection and HTML renderer.
- `code/build_fingoose_company_impact_high_quality_v2.py`: end-to-end CLI builder.
- `configs/company_impact_high_quality_v2/company_registry.jsonl`: 23 unique companies.
- `configs/company_impact_high_quality_v2/event_company_map.jsonl`: 30 event-company rows.
- `configs/company_impact_high_quality_v2/company_claims.jsonl`: claim-level curated facts.
- `configs/company_impact_high_quality_v2/source_manifest.jsonl`: official source metadata.
- `configs/company_impact_high_quality_v2/direction_reviews.jsonl`: AI desk-review candidates.
- `configs/company_impact_high_quality_v2/confounders.jsonl`: structured competing events.
- `configs/company_impact_high_quality_v2/benchmark_registry.jsonl`: CSI300, Shenwan, and ETF proxy declarations.
- `tests/test_fingoose_company_impact_io_v2.py`
- `tests/test_fingoose_company_impact_lineage_v2.py`
- `tests/test_fingoose_company_impact_evidence_v2.py`
- `tests/test_fingoose_company_impact_direction_v2.py`
- `tests/test_fingoose_company_impact_market_v2.py`
- `tests/test_fingoose_company_impact_confounders_v2.py`
- `tests/test_fingoose_company_impact_ui_v2.py`
- `tests/test_build_fingoose_company_impact_high_quality_v2.py`

**Generate only:**

- `work/company_impact_high_quality_v2_candidate/*.jsonl`
- `work/company_impact_high_quality_v2_candidate/*.json`
- `work/company_impact_high_quality_v2_candidate/sources/*`
- `work/company_impact_high_quality_v2_candidate/ui/index.html`
- `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

## Task 1: Canonical I/O and Stable IDs

**Files:**

- Create: `code/fingoose_company_impact_io_v2.py`
- Create: `tests/test_fingoose_company_impact_io_v2.py`

- [ ] **Step 1: Write the failing stable-ID and JSONL tests**

```python
from fingoose_company_impact_io_v2 import make_id, read_jsonl, write_jsonl

def test_make_id_is_order_stable():
    assert make_id("company", {"code": "600009.SH", "name": "上海机场"}) == make_id(
        "company", {"name": "上海机场", "code": "600009.SH"}
    )

def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "rows.jsonl"
    write_jsonl(path, [{"company_name": "上海机场", "status": None}])
    assert read_jsonl(path) == [{"company_name": "上海机场", "status": None}]
```

- [ ] **Step 2: Run the test and verify import failure**

Run: `python -m unittest tests.test_fingoose_company_impact_io_v2 -v`

Expected: `ModuleNotFoundError: fingoose_company_impact_io_v2`.

- [ ] **Step 3: Implement canonical I/O and IDs**

```python
def make_id(prefix: str, value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
```

- [ ] **Step 4: Run the test and record the checkpoint**

Run: `python -m unittest tests.test_fingoose_company_impact_io_v2 -v`

Expected: 2 tests pass. Record `TASK_1=PASS` in the working validation notes; no Git commit is possible.

## Task 2: Freeze 23 Companies and 30 Event Mappings

**Files:**

- Create: `code/fingoose_company_impact_lineage_v2.py`
- Create: `configs/company_impact_high_quality_v2/company_registry.jsonl`
- Create: `configs/company_impact_high_quality_v2/event_company_map.jsonl`
- Create: `tests/test_fingoose_company_impact_lineage_v2.py`

- [ ] **Step 1: Write failing cardinality and lineage tests**

```python
def test_registry_has_23_unique_companies_and_map_has_30_pairs():
    companies = read_jsonl(CONFIG / "company_registry.jsonl")
    mappings = read_jsonl(CONFIG / "event_company_map.jsonl")
    assert len(companies) == 23
    assert len({row["company_id"] for row in companies}) == 23
    assert len(mappings) == 30
    assert len({(row["event_id"], row["company_id"]) for row in mappings}) == 30

def test_each_mapping_resolves_upstream_lineage():
    result = validate_lineage(CONFIG, UPSTREAM)
    assert result["orphan_ids"] == []
    assert result["cross_event_refs"] == []
```

- [ ] **Step 2: Run and observe failure for missing registry**

Run: `python -m unittest tests.test_fingoose_company_impact_lineage_v2 -v`

Expected: failure because the two config files do not exist.

- [ ] **Step 3: Derive the unique registry from the existing 30-row candidate registry**

Use `data/company_candidate_v1/candidate_company_registry.jsonl` as the frozen selection. Preserve all 30 event-company pairs and deduplicate only the master company rows. Assign `company_id` from normalized A-share code, not company name.

- [ ] **Step 4: Resolve each mapping to event, anchor, binding, and industry IDs**

```python
required = (
    "event_id", "anchor_id", "binding_id", "industry_impact_id",
    "company_id", "selection_cutoff_at", "price_selection_used",
)
assert mapping["price_selection_used"] is False
assert mapping["event_id"] == industry_row["event_id"]
assert mapping["anchor_id"] == industry_row["anchor_id"]
assert mapping["binding_id"] in industry_row["binding_ids"]
```

If an existing company row points to an unlinked industry candidate, retain it with `lineage_status=UNLINKED_CANDIDATE` and `evaluation_eligible=false`; do not invent a binding.

- [ ] **Step 5: Run lineage tests**

Run: `python -m unittest tests.test_fingoose_company_impact_lineage_v2 -v`

Expected: all tests pass; output reports 23 companies, 30 mappings, and explicit unlinked rows rather than orphan references.

## Task 3: Claim-Level Evidence Contracts

**Files:**

- Create: `code/fingoose_company_impact_evidence_v2.py`
- Create: `configs/company_impact_high_quality_v2/company_claims.jsonl`
- Create: `configs/company_impact_high_quality_v2/source_manifest.jsonl`
- Create: `tests/test_fingoose_company_impact_evidence_v2.py`

- [ ] **Step 1: Write failing evidence-gate tests**

```python
def test_verified_claim_requires_two_official_disclosures():
    result = evaluate_claim(claim(), [official("annual"), official("ir")], cutoff="2022-02-24T00:00:00Z")
    assert result["verification_status"] == "VERIFIED"

def test_one_source_is_partial_and_future_source_is_hidden():
    partial = evaluate_claim(claim(), [official("annual")], cutoff="2022-02-24T00:00:00Z")
    assert partial["verification_status"] == "PARTIALLY_VERIFIED"
    future = evaluate_claim(claim(), [official("annual", published_at="2023-01-01")], cutoff="2022-02-24T00:00:00Z")
    assert future["availability_scope"] == "VERIFICATION_ONLY"
```

- [ ] **Step 2: Run and verify missing implementation**

Run: `python -m unittest tests.test_fingoose_company_impact_evidence_v2 -v`

Expected: import or symbol failure.

- [ ] **Step 3: Implement source and claim validation**

Require `source_url`, `document_title`, `issuer`, `published_at`, `reporting_period`, `original_quote`, and `page_or_section_locator`. Official source classes are annual report, interim report, exchange filing, prospectus, company IR record, and company website disclosure. Media and broker research never count toward the two-source gate.

- [ ] **Step 4: Implement prediction visibility**

```python
availability_scope = (
    "PREDICTION_VISIBLE" if published_at <= selection_cutoff_at
    else "VERIFICATION_ONLY"
)
```

Only `PREDICTION_VISIBLE` evidence may support public direction inputs. Later reports remain available to hidden validation and counterevidence audit.

- [ ] **Step 5: Run evidence tests**

Run: `python -m unittest tests.test_fingoose_company_impact_evidence_v2 -v`

Expected: all tests pass, including missing locator, mismatched issuer, and post-cutoff isolation cases.

## Task 4: Collect and Verify 23 Master Dossiers

**Files:**

- Modify: `configs/company_impact_high_quality_v2/company_claims.jsonl`
- Modify: `configs/company_impact_high_quality_v2/source_manifest.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/sources/*`
- Generate: `work/company_impact_high_quality_v2_candidate/company_master_dossiers.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/company_evidence.jsonl`

- [ ] **Step 1: Audit reusable official evidence already on disk**

Inspect existing CNINFO snapshots and official intake manifests. Reuse only records whose issuer, reporting period, visible text, locator, and URL match the claim. Do not count the same document twice because it has multiple URLs.

- [ ] **Step 2: Research transport and hospitality companies**

Complete `600009.SH`, `601111.SH`, `600754.SH`, and `601021.SH`. Capture at least one annual or interim report plus one independent official disclosure per company, with claims for business, geographic exposure, demand/cost channel, and limitations.

- [ ] **Step 3: Research energy, chemicals, and shipping companies**

Complete `601857.SH`, `601233.SH`, `600346.SH`, `600028.SH`, `000301.SZ`, and `601919.SH` with the same minimum gate.

- [ ] **Step 4: Research finance and real-estate companies**

Complete `601318.SH`, `600036.SH`, `601988.SH`, `601211.SH`, `600048.SH`, and `300059.SZ` with the same minimum gate.

- [ ] **Step 5: Research healthcare companies**

Complete `002030.SZ`, `002432.SZ`, `300482.SZ`, and `688235.SH` with the same minimum gate.

- [ ] **Step 6: Research manufacturing and trade-exposed companies**

Complete `601012.SH`, `002475.SZ`, and `000333.SZ` with the same minimum gate.

- [ ] **Step 7: Build dossiers without manufacturing missing facts**

```python
dossier_status = (
    "VERIFIED" if core_claims_verified and official_document_count >= 2
    else "PARTIALLY_VERIFIED" if official_document_count >= 1
    else "DATA_PENDING"
)
```

Keep region revenue, cost sensitivity, contract hedges, or exposure shares null when not disclosed. Each null requires a precise `gap_reason`.

- [ ] **Step 8: Validate dossier coverage**

Run: `python -m unittest tests.test_fingoose_company_impact_evidence_v2 -v`

Expected: 23 dossiers emitted, all with at least two official documents for full completion; any exception is explicit and cannot be `VERIFIED`.

## Task 5: Build 30 Direction Assessments

**Files:**

- Create: `code/fingoose_company_impact_direction_v2.py`
- Create: `configs/company_impact_high_quality_v2/direction_reviews.jsonl`
- Create: `tests/test_fingoose_company_impact_direction_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/event_company_exposures.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/direction_assessments.jsonl`

- [ ] **Step 1: Write failing direction and leakage tests**

```python
def test_ai_direction_never_becomes_truth():
    row = build_direction(mapping(), claims(), industry())
    assert row["review_origin"] == "AI_DESK_REVIEW"
    assert row["review_status"] == "NEEDS_HUMAN_REVIEW"
    assert row["hidden_label_eligible"] is False

def test_post_event_price_cannot_support_direction():
    with self.assertRaisesRegex(ValueError, "POST_EVENT_PRICE_LEAKAGE"):
        build_direction(mapping(), claims(), industry(), evidence=[{"kind": "PRICE_OUTCOME"}])
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_fingoose_company_impact_direction_v2 -v`

Expected: missing module or function failure.

- [ ] **Step 3: Implement three-horizon direction records**

Each record contains `IMMEDIATE`, `SHORT_TERM`, and `MEDIUM_TERM`, with allowed values `POSITIVE`, `NEGATIVE`, `MIXED`, `NEUTRAL`, and `UNKNOWN`. Store exposure type, mechanism, lag, conditions, invalidation conditions, claim IDs, counterevidence IDs, rationale, confidence, and review status.

- [ ] **Step 4: Curate all 30 AI desk reviews**

For each event-company pair, write a concise mechanism derived only from event-visible evidence. Preserve `UNKNOWN` when upstream industry lineage is unlinked or company exposure is insufficient. Do not infer a favorable direction from observed price performance.

- [ ] **Step 5: Run direction tests and count checks**

Run: `python -m unittest tests.test_fingoose_company_impact_direction_v2 -v`

Expected: 30 records, all `NEEDS_HUMAN_REVIEW`, zero price-derived rationales, and zero hidden-label eligibility.

## Task 6: Market Windows and Relative Returns

**Files:**

- Create: `code/fingoose_company_impact_market_v2.py`
- Create: `configs/company_impact_high_quality_v2/benchmark_registry.jsonl`
- Create: `tests/test_fingoose_company_impact_market_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/company_market_windows.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/relative_return_windows.jsonl`
- Generate: `work/company_impact_high_quality_v2_candidate/market_source_registry.jsonl`

- [ ] **Step 1: Write failing T0 and relative-return tests**

```python
def test_after_close_rolls_t0_to_next_session():
    assert align_t0("2022-02-24T17:00:00+08:00", sessions)["T0"] == "2022-02-25"

def test_relative_return_uses_same_dates():
    result = relative_return(company=(100, 108), benchmark=(200, 210))
    self.assertAlmostEqual(result, 0.08 - 0.05)

def test_missing_industry_is_not_zero():
    assert build_relative_window(company_window, None)["industry_relative_return"] is None
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_fingoose_company_impact_market_v2 -v`

Expected: missing module or symbol failure.

- [ ] **Step 3: Implement session alignment and formulas**

Output `T_MINUS_1`, `T0`, `D1`, `D3`, `D5`, and `D20`. Preserve target date, actual date, raw close, forward-adjusted close, session offset, source, and formula inputs. Never interpolate across missing bars.

- [ ] **Step 4: Add the reusable CSI300 benchmark**

Collect one CSI300 daily series covering every event window and reuse it for all 30 rows. Calculate:

```python
r_company = company_b / company_a - 1
r_csi300 = csi300_b / csi300_a - 1
ar_market = r_company - r_csi300
```

- [ ] **Step 5: Add Shenwan or explicit ETF proxy**

Use event-date Shenwan L1 history when available. Otherwise select a declared industry ETF only when the registry contains `benchmark_type=ETF_PROXY`, ticker, rationale, effective dates, and source. If no valid proxy exists, emit `DATA_PENDING` and null relative return.

- [ ] **Step 6: Reuse and audit existing 30 company windows**

Reuse `work/verifiable_evaluation_phase1_v2_candidate/company_price_windows.jsonl` only after checking ticker, event, anchor, date range, adjustment, and snapshot. Preserve existing public-vendor licence restrictions.

- [ ] **Step 7: Run market tests and recomputation checks**

Run: `python -m unittest tests.test_fingoose_company_impact_market_v2 -v`

Expected: every non-null return recomputes from stored values, CSI300 is present for all valid company windows, and missing industry benchmarks remain null rather than zero.

## Task 7: Suspension, Confounders, and Counterevidence

**Files:**

- Create: `code/fingoose_company_impact_confounders_v2.py`
- Create: `configs/company_impact_high_quality_v2/confounders.jsonl`
- Create: `tests/test_fingoose_company_impact_confounders_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/company_confounders.jsonl`

- [ ] **Step 1: Write failing gate tests**

```python
def test_missing_bar_does_not_imply_suspension():
    result = classify_suspension(missing_bar=True, exchange_notice=None)
    assert result == "UNVERIFIED"

def test_material_confounder_excludes_clean_score():
    assert score_eligibility("MATERIAL") == "CHALLENGE_ONLY"
    assert score_eligibility("DOMINANT") == "CHALLENGE_ONLY"
    assert score_eligibility("UNRESOLVED") == "CHALLENGE_ONLY"
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_fingoose_company_impact_confounders_v2 -v`

Expected: missing module or symbol failure.

- [ ] **Step 3: Implement suspension evidence rules**

Exchange announcements are primary evidence and trusted trading bars are cross-checks. Store first tradable day and offset. A stale close across suspension cannot be treated as a normal event observation; mark `WINDOW_CONTAMINATED`.

- [ ] **Step 4: Research event-, industry-, and company-level confounders**

For each of 30 rows, inspect the T-1 through D20 interval for macro releases, sector shocks, earnings, forecasts, M&A, buybacks, ownership changes, litigation, major contracts, and suspension/resumption. Every registered item needs occurred/public times, source, quote, locator, mechanism, affected windows, severity, and disposition.

- [ ] **Step 5: Register counterevidence separately**

Natural hedges, fixed-price contracts, low segment share, or management statements of limited impact must not be merged into support evidence. If none is found, write `NO_COUNTEREVIDENCE_FOUND` plus search scope; never write “counterevidence does not exist.”

- [ ] **Step 6: Run confounder tests**

Run: `python -m unittest tests.test_fingoose_company_impact_confounders_v2 -v`

Expected: all grades are valid, challenge-only rows cannot enter clean scoring, and every non-clean item has evidence and an affected window.

## Task 8: End-to-End Builder and Release Gates

**Files:**

- Create: `code/build_fingoose_company_impact_high_quality_v2.py`
- Create: `tests/test_build_fingoose_company_impact_high_quality_v2.py`
- Generate: all package JSON/JSONL, `README.md`, `summary.json`, `validation_report.json`, and `manifest.json`.

- [ ] **Step 1: Write failing end-to-end tests**

```python
def test_build_emits_expected_cardinality(tmp_path):
    report = build(ROOT, tmp_path / "candidate")
    assert report["company_count"] == 23
    assert report["event_company_count"] == 30
    assert report["orphan_id_count"] == 0
    assert report["formal_ready"] is False
    assert report["sha_gate"] == "DEFERRED"

def test_ai_reviews_never_leak_to_labels(tmp_path):
    build(ROOT, tmp_path / "candidate")
    public = (tmp_path / "candidate" / "ui" / "ui_data_bundle.js").read_text(encoding="utf-8")
    assert "benchmark_labels" not in public
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_build_fingoose_company_impact_high_quality_v2 -v`

Expected: builder import failure.

- [ ] **Step 3: Implement deterministic orchestration**

Build in this order: lineage, evidence, dossiers, event exposures, direction, market windows, relative returns, confounders, validation, UI projection, summary, and manifest. A record-level external-data gap becomes a warning/status; cross-event references, invalid JSON, price leakage, unverifiable arithmetic, or public hidden-label leakage become hard failures.

- [ ] **Step 4: Run the candidate builder**

Run: `python code/build_fingoose_company_impact_high_quality_v2.py`

Expected: output is written only under `work/company_impact_high_quality_v2_candidate/`; existing candidate directories remain unchanged.

- [ ] **Step 5: Run end-to-end tests**

Run: `python -m unittest tests.test_build_fingoose_company_impact_high_quality_v2 -v`

Expected: all tests pass and `formal_ready=false` remains explicit.

## Task 9: Integrated Chinese UI

**Files:**

- Create: `code/fingoose_company_impact_ui_v2.py`
- Create: `tests/test_fingoose_company_impact_ui_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [ ] **Step 1: Write failing UI projection tests**

```python
def test_event_projection_contains_full_company_chain():
    event = project_event(bundle(), "event-02")
    assert event["timeline"]
    assert event["transmission_paths"]
    assert event["industries"]
    assert len(event["companies"]) == 3
    assert all(row["lineage"] for row in event["companies"])

def test_file_page_does_not_fetch_cross_directory_json():
    html = render_workbench(bundle())
    assert "fetch(" not in html
    assert "ui_data_bundle.js" in html
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_fingoose_company_impact_ui_v2 -v`

Expected: missing renderer failure.

- [ ] **Step 3: Implement event-to-company interactions**

Keep the ten-event left sidebar. Add linked sections for event timeline, transmission graph, industry impact, company cards, dossier drawer, three-horizon direction, price/benchmark chart, absolute-value table, confounder argument, and counterevidence. Clicking a timeline node filters bindings, industries, and companies through stable IDs.

- [ ] **Step 4: Implement explicit data states**

Render `DATA_PENDING`, `PARTIALLY_VERIFIED`, `NEEDS_HUMAN_REVIEW`, `ETF_PROXY`, `UNVERIFIED`, and `WINDOW_CONTAMINATED` in Chinese. Null values display “数据待补”, never `0`.

- [ ] **Step 5: Run UI unit tests**

Run: `python -m unittest tests.test_fingoose_company_impact_ui_v2 -v`

Expected: event-02 contains three linked companies, evidence links and formulas are present, and the page is file-compatible.

- [ ] **Step 6: Perform desktop and mobile visual QA**

Serve the UI locally, capture desktop and mobile screenshots, and verify no overlap, clipped Chinese text, blank chart, or broken evidence links. Confirm `file://.../ui/index.html` also renders the embedded data.

## Task 10: Full Verification and Handoff

**Files:**

- Modify: `work/company_impact_high_quality_v2_candidate/README.md`
- Modify: `work/company_impact_high_quality_v2_candidate/summary.json`
- Modify: `work/company_impact_high_quality_v2_candidate/validation_report.json`

- [ ] **Step 1: Run focused v2 tests**

Run:

```powershell
python -m unittest `
  tests.test_fingoose_company_impact_io_v2 `
  tests.test_fingoose_company_impact_lineage_v2 `
  tests.test_fingoose_company_impact_evidence_v2 `
  tests.test_fingoose_company_impact_direction_v2 `
  tests.test_fingoose_company_impact_market_v2 `
  tests.test_fingoose_company_impact_confounders_v2 `
  tests.test_fingoose_company_impact_ui_v2 `
  tests.test_build_fingoose_company_impact_high_quality_v2 -v
```

Expected: all focused tests pass.

- [ ] **Step 2: Run relevant regression tests**

Run:

```powershell
python -m unittest `
  tests.test_build_fingoose_ten_event_rapid_candidate_v2 `
  tests.test_fingoose_public_company_price_windows_v1 `
  tests.test_fingoose_event_industry_impact_v1 -v
```

Expected: existing timeline, market, and industry tests still pass.

- [ ] **Step 3: Parse and count every output**

Validate every JSON/JSONL file, verify 23 unique `company_id`, 30 unique `(event_id, company_id)`, no orphan lineage, and no null represented as zero. Recompute every non-null company and relative return from stored inputs.

- [ ] **Step 4: Check publication boundaries**

Verify `formal_ready=false`, `sha_gate=DEFERRED`, all AI direction rows are `NEEDS_HUMAN_REVIEW`, proprietary raw data is not included in redistributable output, and hidden labels are absent from `ui_data_bundle.js`.

- [ ] **Step 5: Finalize the handoff report**

Document verified dossier count, partial dossier count, direction-review count, CSI300 coverage, Shenwan coverage, ETF proxy count, suspension status counts, confounder grade counts, hard failures, warnings, and the exact UI path. Do not report a missing field as completed.
