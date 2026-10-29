# FinGoose SFT Dataset Release Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing ten-event `sft_dataset.jsonl` a strictly validated, hash-bound, deterministic standard `messages` SFT release artifact.

**Architecture:** Extend the pure-Python validator with explicit schema, coverage, reference, content-length, and truncation gates. Bind `validation_report.json` to the exact generated artifacts through SHA-256 values, and make training data readiness reject stale reports while remaining independent of CUDA and model dependencies.

**Tech Stack:** Python 3.12 standard library, JSON/JSONL, pytest.

---

## Version Control Note

The workspace is not a valid Git repository, so the commit steps normally required by the planning workflow are omitted. All edits remain scoped to the existing `training/` module and its design documentation.

### Task 1: Strengthen the SFT schema and coverage gates

**Files:**
- Modify: `training/tests/test_validation.py`
- Modify: `training/fingoose_training/validation.py`
- Modify: `training/scripts/validate_dataset.py`

- [ ] **Step 1: Add failing tests for task, event, split, and message contracts**

Add tests that call `validate_datasets(..., expected_task_types=...)` and assert stable error codes for:

```python
MISSING_TASK_COVERAGE
MISSING_SAMPLE_EVENT_COVERAGE
INVALID_SPLIT
INVALID_MESSAGE_CONTENT
```

The message test must cover empty `system`, empty `user`, non-string `content`, and preserve the existing empty-assistant behavior.

- [ ] **Step 2: Run validation tests and verify RED**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_validation.py -q
```

Expected: new tests fail because the gates and optional `expected_task_types` argument do not exist.

- [ ] **Step 3: Implement the minimal schema and coverage checks**

Extend the API to:

```python
def validate_datasets(
    unified_events: list[dict[str, Any]],
    sft_samples: list[dict[str, Any]],
    expected_events: set[str],
    expected_task_types: set[str] | None = None,
) -> dict[str, Any]:
```

Require allowed split names, all expected tasks, at least one sample for every expected event, exact three-role messages, and non-empty string role/content values. Pass configured task types from `validate_dataset.py`.

- [ ] **Step 4: Run validation tests and verify GREEN**

Run the Task 1 test command and confirm all tests pass.

### Task 2: Validate metadata references and trainable content limits

**Files:**
- Modify: `training/tests/test_validation.py`
- Modify: `training/fingoose_training/validation.py`

- [ ] **Step 1: Add failing reference and content tests**

Add independent tests for:

```python
UNKNOWN_RELATED_INDUSTRY
UNKNOWN_RELATED_COMPANY
INVALID_METADATA_LIST
HARD_TRUNCATION_MARKER
MESSAGE_LENGTH_EXCEEDED
```

Use the literal marker `[内容已按训练长度上限截断]` and a three-message total over 2000 characters.

- [ ] **Step 2: Run the new tests and verify RED**

Run `python -m pytest training/tests/test_validation.py -q` with `PYTHONPATH=training` and confirm failures are caused by missing gates.

- [ ] **Step 3: Implement event-local reference and content validation**

Build event-local sets of `event_industry_mapping_id` and `company_code`. Require the four metadata lineage fields to be lists of strings, validate industry/company values against the same unified event, reject the hard truncation marker, and reject total message content above 2000 characters.

- [ ] **Step 4: Run the validation tests and verify GREEN**

Confirm the full validation test module passes without warnings or errors.

### Task 3: Bind validation reports to generated artifact hashes

**Files:**
- Modify: `training/tests/test_build_cli.py`
- Modify: `training/tests/test_training_cli.py`
- Modify: `training/scripts/validate_dataset.py`
- Modify: `training/scripts/train_sft.py`

- [ ] **Step 1: Add failing report-binding tests**

Require `validation_report.json` to contain:

```json
{
  "dataset_version": "...",
  "validated_artifacts": {
    "unified_events": {"sha256": "..."},
    "sft_dataset": {"sha256": "..."},
    "split_manifest": {"sha256": "..."}
  }
}
```

Add a training readiness test that changes the report's SFT hash and expects `ready=false` with a stale-report error.

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_build_cli.py training/tests/test_training_cli.py -q
```

- [ ] **Step 3: Write artifact hashes during validation and enforce them during readiness**

Use the existing `sha256_file` helper. Keep readiness scoped to data validity; do not check CUDA, model downloads, or optional training packages.

- [ ] **Step 4: Run CLI tests and verify GREEN**

Confirm the Task 3 test command passes.

### Task 4: Add a real-dataset release regression

**Files:**
- Modify: `training/tests/test_sft_real_dataset.py`

- [ ] **Step 1: Extend the real-data test with release invariants**

Load both real JSONL files and assert:

- 10 unified events and 157 SFT samples.
- Exact four-task coverage.
- No empty message content or hard truncation marker.
- All event-local industry/company references resolve.
- Every message bundle fits within 2000 characters.

- [ ] **Step 2: Run the real-data test**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_sft_real_dataset.py -q
```

Expected: PASS against the current generated dataset.

### Task 5: Rebuild, validate, document, and verify determinism

**Files:**
- Modify: `training/README.md`
- Regenerate: `training/data/unified_events.jsonl`
- Regenerate: `training/data/sft_dataset.jsonl`
- Regenerate: `training/data/split_manifest.json`
- Regenerate: `training/data/manifest.json`
- Regenerate: `training/data/validation_report.json`

- [ ] **Step 1: Update README release semantics**

Document that readiness means data readiness, list the strengthened gates, and state that CUDA/model environment checks are outside dataset validation.

- [ ] **Step 2: Rebuild and validate real data**

Run the unified builder, SFT builder, and validator in that order. Require 10 events, 157 samples, and zero errors/warnings.

- [ ] **Step 3: Run the complete training test suite and compile check**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
```

- [ ] **Step 4: Verify deterministic reconstruction**

Rebuild both core JSONL files twice and compare SHA-256 values. Both before/after pairs must be identical.

- [ ] **Step 5: Run final data readiness**

Run `train_sft.py --dry-run`. Require `ready=true`, a current SFT SHA-256, and the unchanged split counts 124/16/17. This confirms only data readiness and does not claim the local CUDA environment can train.
