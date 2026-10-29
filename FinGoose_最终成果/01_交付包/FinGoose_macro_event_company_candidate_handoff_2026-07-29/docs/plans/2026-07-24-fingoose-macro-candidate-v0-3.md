# FinGoose Macro Candidate v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and verify 10 point-in-time macro case groups and 20 public-official-only sector/company predictions using information visible by 2025-03-31.

**Architecture:** A fixed case map selects official evidence from the validated source foundation, creates paired sector-transmission and company-event records, and keeps Q2/H1 outcomes in a separate hidden verification layer. Deterministic validators enforce evidence coverage, cutoff isolation, structured reasoning steps, scoring, and positive/negative training projection.

**Tech Stack:** Python 3.12, standard library, `jsonschema 4.23.0`, `unittest`.

---

### Task 1: Define Macro Record and Verification Schemas

**Files:**
- Create: `schemas/fingoose_macro_candidate_v0_3.schema.json`
- Create: `schemas/fingoose_forecast_verification_v0_3.schema.json`
- Create: `tests/test_fingoose_macro_candidate_v0_3.py`

- [ ] **Step 1: Write a failing schema test for required prediction fields**

```python
def test_macro_schema_requires_actionable_prediction_fields(self):
    record = minimal_macro_record()
    del record["prediction"]["direction"]
    with self.assertRaises(jsonschema.ValidationError):
        jsonschema.validate(record, self.schema)
```

- [ ] **Step 2: Run and verify the schema file is missing**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroSchemaTests -v`

Expected: `FileNotFoundError`.

- [ ] **Step 3: Create strict schemas**

The macro schema must require:

```text
sample_id, case_group_id, dataset_version, task_type, cutoff_at,
entity, question, evidence_items, tool_trace, prediction,
counterevidence, invalidation_conditions, provenance, quality
```

`task_type` is `sector_transmission` or `company_event_forecast`. `prediction` requires direction, horizon, target, threshold, confidence, and commentary. Evidence requires `source_id`, `published_at`, `model_visible=true`, locator, statement, and source family. The verification schema requires `verification_label`, `reasoning_valid`, hidden outcome references, score components, and error types.

- [ ] **Step 4: Run schema tests**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroSchemaTests -v`

Expected: valid fixtures pass and missing actionable fields fail.

### Task 2: Configure the 10 Case Groups

**Files:**
- Create: `configs/fingoose_macro_cases_v0_3.json`
- Modify: `tests/test_fingoose_macro_candidate_v0_3.py`

- [ ] **Step 1: Write a failing case-map coverage test**

```python
def test_case_map_has_ten_unique_companies_and_required_drivers(self):
    cases = load_json(CONFIG)["cases"]
    self.assertEqual(len(cases), 10)
    self.assertEqual(len({case["company_code"] for case in cases}), 10)
    self.assertTrue(all(len(case["required_source_families"]) >= 3 for case in cases))
    self.assertTrue(all(case["cutoff_at"] == "2025-03-31T23:59:59+08:00" for case in cases))
```

- [ ] **Step 2: Run and confirm the configuration is missing**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroCaseConfigTests -v`

Expected: `FileNotFoundError`.

- [ ] **Step 3: Add the fixed case map**

Configure these mappings:

```text
000002.SZ 万科A       -> 房地产销售、融资和减值
002244.SZ 滨江集团    -> 房地产销售、拿地和现金回款
300750.SZ 宁德时代    -> 新能源汽车需求和动力电池
600010.SH 包钢股份    -> 钢材需求、钢价和原料成本
600019.SH 宝钢股份    -> 钢材需求、产品结构和购销价差
600346.SH 恒力石化    -> 原油、炼化价差和化工需求
600438.SH 通威股份    -> 光伏供需、硅料价格和减值
601233.SH 桐昆股份    -> 涤纶长丝、原料价格和价差
601857.SH 中国石油    -> 国际油价、产量和炼化业务
688676.SH 金盘科技    -> 电网投资、新能源装机和订单
```

Each case specifies sector, business exposures, visible company-source requirement, macro source families, one counterevidence family, company target metric/event, sector target, verification window, and hidden H1 report source requirement.

- [ ] **Step 4: Run case-map tests**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroCaseConfigTests -v`

Expected: exactly 10 complete and unique case definitions pass.

### Task 3: Select Point-in-Time Evidence

**Files:**
- Create: `fingoose_macro_candidate_v0_3.py`
- Modify: `tests/test_fingoose_macro_candidate_v0_3.py`

- [ ] **Step 1: Write failing evidence-selection tests**

```python
def test_select_evidence_rejects_future_and_vendor_sources(self):
    rows = fixture_evidence()
    rows.append(evidence(source_id="FUTURE", published_at="2025-04-01T00:00:00+08:00"))
    rows.append(evidence(source_id="WIND", source_url="http://news.windin.com/a.pdf"))
    selected = select_case_evidence(self.case, rows, cutoff_at=MACRO_CUTOFF)
    self.assertNotIn("FUTURE", {item["source_id"] for item in selected})
    self.assertNotIn("WIND", {item["source_id"] for item in selected})
    self.assertGreaterEqual(len(selected), 6)
    self.assertGreaterEqual(len({item["source_family"] for item in selected}), 3)
```

- [ ] **Step 2: Run and verify selection is missing**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroEvidenceTests -v`

Expected: import failure for `select_case_evidence`.

- [ ] **Step 3: Implement fail-closed selection**

```python
def select_case_evidence(case, evidence_rows, cutoff_at):
    eligible = [
        row for row in evidence_rows
        if row["published_at"] <= cutoff_at
        and row["source_policy"] == "public_official_only"
        and not row["quality_flags"]
    ]
    selected = select_required_families(case, eligible)
    if len(selected) < 6:
        raise MacroBuildError("INSUFFICIENT_EVIDENCE_COUNT")
    if len({row["source_family"] for row in selected}) < 3:
        raise MacroBuildError("INSUFFICIENT_SOURCE_DIVERSITY")
    if not any(row["evidence_role"] == "counterevidence" for row in selected):
        raise MacroBuildError("COUNTEREVIDENCE_MISSING")
    return selected
```

- [ ] **Step 4: Run evidence tests**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroEvidenceTests -v`

Expected: cutoff, policy, evidence-count, source-family, and counterevidence tests pass.

### Task 4: Generate Paired Sector and Company Predictions

**Files:**
- Modify: `fingoose_macro_candidate_v0_3.py`
- Create: `build_fingoose_macro_candidate_v0_3.py`
- Modify: `tests/test_fingoose_macro_candidate_v0_3.py`

- [ ] **Step 1: Write failing paired-record tests**

```python
def test_build_case_group_returns_sector_and_company_records(self):
    records = build_case_group(self.case, self.evidence)
    self.assertEqual([row["task_type"] for row in records], [
        "sector_transmission", "company_event_forecast"
    ])
    self.assertEqual(len({row["case_group_id"] for row in records}), 1)
    for row in records:
        self.assertIn(row["prediction"]["direction"], {"positive", "negative", "mixed", "uncertain"})
        self.assertTrue(row["prediction"]["target"])
        self.assertTrue(row["prediction"]["threshold"])
        self.assertTrue(row["invalidation_conditions"])
```

- [ ] **Step 2: Run and verify paired generation is missing**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroGenerationTests -v`

Expected: import failure for `build_case_group`.

- [ ] **Step 3: Implement deterministic record assembly**

Each record uses six structured steps: cutoff confirmation, macro fact extraction, company exposure, deterministic metric calculation, counterevidence, and conclusion. The commentary is a concise evidence summary with citations, not unrestricted chain-of-thought. IDs are SHA-256-derived from dataset version, case code, and task type.

The CLI reads the source manifest, page evidence, case config, and schemas, then writes:

```text
outputs/fingoose_research_candidate_v0_3/macro_case_groups_10.jsonl
outputs/fingoose_research_candidate_v0_3/macro_predictions_20.jsonl
outputs/fingoose_research_candidate_v0_3/macro_rejected.jsonl
```

- [ ] **Step 4: Run generation tests**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3.MacroGenerationTests -v`

Expected: deterministic IDs, paired records, actionable targets, and structured citations pass.

### Task 5: Verify Forecast Outcomes without Leakage

**Files:**
- Create: `fingoose_forecast_verifier_v0_3.py`
- Create: `tests/test_fingoose_forecast_verifier_v0_3.py`

- [ ] **Step 1: Write failing scoring tests**

```python
def test_score_forecast_separates_reasoning_and_outcome(self):
    result = score_forecast(
        predicted_direction="negative",
        realized_direction="negative",
        target_hit=True,
        timing_hit=False,
        reasoning_valid=True,
    )
    self.assertEqual(result["verification_label"], "partial")
    self.assertTrue(result["reasoning_valid"])
    self.assertIn("timing_error", result["error_types"])
```

- [ ] **Step 2: Run and verify the verifier is missing**

Run: `python -m unittest tests.test_fingoose_forecast_verifier_v0_3 -v`

Expected: import failure for `score_forecast`.

- [ ] **Step 3: Implement deterministic labels**

Use these rules:

```text
correct      = direction_hit and target_hit and timing_hit
partial      = direction_hit and (target_hit or timing_hit), but not correct
incorrect    = outcome available and not direction_hit
unverifiable = outcome source absent or target cannot be measured
```

Keep `reasoning_valid` independent. Outcome evidence must have `model_visible=false`, `published_at > cutoff_at`, and official-source policy. Validation must reject any outcome evidence copied into prediction evidence.

- [ ] **Step 4: Run verifier tests**

Run: `python -m unittest tests.test_fingoose_forecast_verifier_v0_3 -v`

Expected: all four labels, error taxonomy, and leakage checks pass.

### Task 6: Create Correct and Incorrect Training Projections

**Files:**
- Modify: `fingoose_forecast_verifier_v0_3.py`
- Modify: `tests/test_fingoose_forecast_verifier_v0_3.py`

- [ ] **Step 1: Write failing projection eligibility tests**

```python
def test_projection_eligibility(self):
    self.assertEqual(project_bucket(label="correct", reasoning_valid=True), "correct")
    self.assertEqual(project_bucket(label="incorrect", reasoning_valid=True), "incorrect")
    self.assertEqual(project_bucket(label="correct", reasoning_valid=False), "incorrect")
    self.assertIsNone(project_bucket(label="partial", reasoning_valid=True))
    self.assertIsNone(project_bucket(label="unverifiable", reasoning_valid=True))
```

- [ ] **Step 2: Run and verify projection logic is missing**

Run: `python -m unittest tests.test_fingoose_forecast_verifier_v0_3.ForecastProjectionTests -v`

Expected: import failure for `project_bucket`.

- [ ] **Step 3: Implement projections**

Correct projection rows preserve the original prediction and evidence summary. Incorrect projection rows preserve the original prediction, error types, official outcome evidence, a short critique, and a corrected target. Partial and unverifiable cases remain only in `forecast_verification.jsonl`.

- [ ] **Step 4: Run projection tests**

Run: `python -m unittest tests.test_fingoose_forecast_verifier_v0_3.ForecastProjectionTests -v`

Expected: eligibility and projection-field tests pass.

### Task 7: Validate the Real 20-Record Build

**Files:**
- Modify: `build_fingoose_macro_candidate_v0_3.py`
- Modify: `tests/test_fingoose_macro_candidate_v0_3.py`

- [ ] **Step 1: Add end-to-end acceptance checks**

The validator must assert 10 case groups, 20 records, 10 records per task type, 6 or more evidence items per record, 3 or more source families, one counterevidence item, zero future-visible evidence, zero paid/vendor sources, unique IDs, valid schemas, and unchanged SHA-256 for existing Canonical outputs.

- [ ] **Step 2: Run the complete macro test suite**

Run: `python -m unittest tests.test_fingoose_macro_candidate_v0_3 tests.test_fingoose_forecast_verifier_v0_3 -v`

Expected: all tests pass.

- [ ] **Step 3: Run the real build**

Run: `python build_fingoose_macro_candidate_v0_3.py --config configs/fingoose_research_candidate_v0_3.json --cases configs/fingoose_macro_cases_v0_3.json`

Expected: exit 0 only when all 20 records pass; otherwise non-zero with exact missing source or evidence requirement in `macro_rejected.jsonl`.

- [ ] **Step 4: Verify published outputs**

Run: `python fingoose_v0_2_cli.py check-readiness`

Expected: v0.2 formal gate remains blocked and `formal_sample_generation_allowed=false`; the v0.3 candidate build must not modify it.

