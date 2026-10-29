# Macro Review Decision Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent, incremental and auditable human-review decision import path, enforce independent second review and adjudication, and remove attribution labels from the public projection.

**Architecture:** Keep event facts and proposed labels in the existing event configuration. Parse a separate review-decision JSONL file, validate each complete audit trail, merge only valid decisions into generated `ReviewRecord` objects, and derive internal samples, hidden labels and release gates from the merged records. Public projections are built through an explicit whitelist and never copy attribution or review fields.

**Tech Stack:** Python 3.12, standard-library JSON/Path/datetime APIs, JSON Schema Draft 2020-12 through `jsonschema`, `unittest`, JSONL artifacts.

**Workspace note:** `D:\桌面\workspace\codex1` is not a Git repository. Version-control commit steps are intentionally omitted; every write remains inside this project directory.

---

## File Map

- Create `schemas/fingoose_macro_review_decision_v1.schema.json`: machine contract for initial, second and adjudication verdicts.
- Create `configs/fingoose_macro_review_decisions_v1.jsonl`: empty incremental human-decision input.
- Modify `schemas/fingoose_macro_review_record_v1.schema.json`: preserve reviewer timestamp, comments and verdict in the audit record.
- Modify `fingoose_macro_event_attribution_v1.py`: pure decision validation, resolution, merge and public-projection functions.
- Modify `build_fingoose_macro_event_attribution_v1.py`: JSONL loading, CLI integration, templates, blind packets and hidden labels.
- Modify `tests/test_fingoose_macro_review_workflow_v1.py`: decision contract, merge, isolation and release tests.
- Modify `tests/test_fingoose_macro_event_attribution_v1.py`: updated ReviewRecord and public-projection expectations.
- Modify `tests/test_fingoose_macro_event_production_config_v1.py`: production counts for new artifacts.
- Modify `docs/fingoose_macro_event_review_handbook_v1.md`: exact reviewer submission workflow.

### Task 1: Define The Review Decision Contract

**Files:**
- Create: `schemas/fingoose_macro_review_decision_v1.schema.json`
- Create: `configs/fingoose_macro_review_decisions_v1.jsonl`
- Modify: `fingoose_macro_event_attribution_v1.py:14-22`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`

- [ ] **Step 1: Write failing Schema tests**

Add these tests to `MacroReviewWorkflowTests`:

```python
def _verdict(self, reviewer_id='reviewer-a', label='PRIMARY_DRIVER', confidence='HIGH'):
    return {
        'reviewer_id': reviewer_id,
        'reviewed_at': '2026-07-27T10:00:00+08:00',
        'comments': 'Timing, abnormal movement and transmission evidence were checked.',
        'label': label,
        'confidence': confidence,
        'core_dimensions': {
            'temporal_alignment': 'SUPPORTED',
            'abnormal_movement': 'SUPPORTED',
            'transmission_mechanism': 'SUPPORTED',
            'competing_explanations': 'LIMITED',
        },
    }

def test_review_decision_schema_requires_complete_initial_verdict(self):
    from fingoose_macro_event_attribution_v1 import validate_schema_record

    decision = {
        'review_id': 'review-event-01-single-sp500',
        'event_id': 'event-01',
        'initial_review': self._verdict(),
        'second_review': None,
        'adjudication': None,
    }
    self.assertEqual(validate_schema_record('review_decision', decision), [])
    decision['initial_review'].pop('comments')
    self.assertTrue(validate_schema_record('review_decision', decision))
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m unittest tests.test_fingoose_macro_review_workflow_v1.MacroReviewWorkflowTests.test_review_decision_schema_requires_complete_initial_verdict -v
```

Expected: error containing `UNKNOWN_RECORD_TYPE:review_decision`.

- [ ] **Step 3: Create the complete decision Schema**

Create a Draft 2020-12 Schema with required top-level fields `review_id`, `event_id`, `initial_review`, `second_review`, and `adjudication`; set `additionalProperties: false`. Define `$defs.core_dimensions` with the existing four enums and `$defs.verdict` with these required properties:

```json
{
  "reviewer_id": {"type": "string", "minLength": 1},
  "reviewed_at": {"type": "string", "format": "date-time"},
  "comments": {"type": "string", "minLength": 1},
  "label": {"enum": ["PRIMARY_DRIVER", "CONTRIBUTING_FACTOR", "WEAK_RELATION", "UNSUPPORTED"]},
  "confidence": {"enum": ["HIGH", "MEDIUM", "LOW"]},
  "core_dimensions": {"$ref": "#/$defs/core_dimensions"}
}
```

Use `anyOf` with `null` or `$defs.verdict` for `second_review` and `adjudication`. Add this entry to `SCHEMA_PATHS`:

```python
'review_decision': ROOT / 'schemas' / 'fingoose_macro_review_decision_v1.schema.json',
```

Create `configs/fingoose_macro_review_decisions_v1.jsonl` as a zero-byte UTF-8 file.

- [ ] **Step 4: Run the focused Schema tests and verify GREEN**

```powershell
python -m unittest tests.test_fingoose_macro_review_workflow_v1.MacroReviewWorkflowTests.test_review_decision_schema_requires_complete_initial_verdict -v
```

Expected: one test passes.

### Task 2: Enforce Review, Independence And Adjudication Rules

**Files:**
- Modify: `fingoose_macro_event_attribution_v1.py:192-223`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`

- [ ] **Step 1: Write failing business-rule tests**

Add three tests:

```python
def test_low_confidence_initial_verdict_requires_independent_second_review(self):
    from fingoose_macro_event_attribution_v1 import review_decision_errors

    initial = self._verdict(confidence='LOW')
    initial['core_dimensions']['competing_explanations'] = 'STRONG'
    decision = {
        'review_id': 'review-event-01-single-dcoilwtico',
        'event_id': 'event-01',
        'initial_review': initial,
        'second_review': None,
        'adjudication': None,
    }
    errors = review_decision_errors(decision, 'event-01', '2026-07-27T23:59:59+08:00')
    self.assertIn('SECOND_REVIEW_REQUIRED', errors)
    decision['second_review'] = copy.deepcopy(initial)
    self.assertIn(
        'SECOND_REVIEWER_NOT_INDEPENDENT',
        review_decision_errors(decision, 'event-01', '2026-07-27T23:59:59+08:00'),
    )

def test_disagreement_requires_independent_adjudicator(self):
    from fingoose_macro_event_attribution_v1 import review_decision_errors

    initial = self._verdict(confidence='LOW')
    second = self._verdict('reviewer-b', label='WEAK_RELATION', confidence='LOW')
    decision = {
        'review_id': 'review-event-01-single-dcoilwtico',
        'event_id': 'event-01',
        'initial_review': initial,
        'second_review': second,
        'adjudication': None,
    }
    self.assertIn(
        'ADJUDICATION_REQUIRED',
        review_decision_errors(decision, 'event-01', '2026-07-27T23:59:59+08:00'),
    )
    decision['adjudication'] = self._verdict('reviewer-b', label='WEAK_RELATION', confidence='LOW')
    self.assertIn(
        'ADJUDICATOR_NOT_INDEPENDENT',
        review_decision_errors(decision, 'event-01', '2026-07-27T23:59:59+08:00'),
    )

def test_matching_verdicts_resolve_without_adjudication(self):
    from fingoose_macro_event_attribution_v1 import resolve_review_decision

    initial = self._verdict(confidence='LOW')
    second = copy.deepcopy(initial)
    second['reviewer_id'] = 'reviewer-b'
    decision = {
        'review_id': 'review-event-01-single-dcoilwtico',
        'event_id': 'event-01',
        'initial_review': initial,
        'second_review': second,
        'adjudication': None,
    }
    final_verdict, reasons = resolve_review_decision(decision)
    self.assertEqual(final_verdict['label'], 'PRIMARY_DRIVER')
    self.assertIn('LOW_CONFIDENCE', reasons)
```

- [ ] **Step 2: Run the three tests and verify RED**

```powershell
python -m unittest `
  tests.test_fingoose_macro_review_workflow_v1.MacroReviewWorkflowTests.test_low_confidence_initial_verdict_requires_independent_second_review `
  tests.test_fingoose_macro_review_workflow_v1.MacroReviewWorkflowTests.test_disagreement_requires_independent_adjudicator `
  tests.test_fingoose_macro_review_workflow_v1.MacroReviewWorkflowTests.test_matching_verdicts_resolve_without_adjudication -v
```

Expected: import errors for `review_decision_errors` and `resolve_review_decision`.

- [ ] **Step 3: Implement pure decision rules**

Add these helpers to `fingoose_macro_event_attribution_v1.py`:

```python
PLACEHOLDER_REVIEWER_IDS = {'PENDING_HUMAN', 'PENDING_SECOND_HUMAN', 'PENDING_ADJUDICATOR'}


def _verdict_payload(verdict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'label': verdict['label'],
        'confidence': verdict['confidence'],
        'core_dimensions': copy.deepcopy(verdict['core_dimensions']),
    }


def _verdicts_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _verdict_payload(left) == _verdict_payload(right)


def _verdict_trigger_reasons(verdict: Mapping[str, Any]) -> list[str]:
    return second_review_trigger_reasons({
        'confidence': verdict['confidence'],
        'core_dimensions': verdict['core_dimensions'],
    })


def review_decision_errors(
    decision: Mapping[str, Any], expected_event_id: str, build_at: str,
) -> list[str]:
    errors = list(validate_schema_record('review_decision', decision))
    if errors:
        return ['REVIEW_DECISION_SCHEMA_INVALID']
    if decision['event_id'] != expected_event_id:
        errors.append('REVIEW_EVENT_MISMATCH')
    build_time = _parse_datetime(build_at)
    verdicts = [decision['initial_review'], decision.get('second_review'), decision.get('adjudication')]
    for verdict in (row for row in verdicts if row is not None):
        if verdict['reviewer_id'] in PLACEHOLDER_REVIEWER_IDS:
            errors.append('INITIAL_REVIEWER_PLACEHOLDER')
        if _parse_datetime(verdict['reviewed_at']) > build_time:
            errors.append('REVIEWED_AT_IN_FUTURE')
    initial = decision['initial_review']
    second = decision.get('second_review')
    adjudication = decision.get('adjudication')
    requires_second = bool(_verdict_trigger_reasons(initial))
    if requires_second and second is None:
        errors.append('SECOND_REVIEW_REQUIRED')
    if second is not None and second['reviewer_id'] == initial['reviewer_id']:
        errors.append('SECOND_REVIEWER_NOT_INDEPENDENT')
    disagrees = second is not None and not _verdicts_equal(initial, second)
    if disagrees and adjudication is None:
        errors.append('ADJUDICATION_REQUIRED')
    if not disagrees and adjudication is not None:
        errors.append('UNNECESSARY_ADJUDICATION')
    if adjudication is not None and adjudication['reviewer_id'] in {
        initial['reviewer_id'], second['reviewer_id'] if second else '',
    }:
        errors.append('ADJUDICATOR_NOT_INDEPENDENT')
    return list(dict.fromkeys(errors))


def resolve_review_decision(decision: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    initial = decision['initial_review']
    second = decision.get('second_review')
    adjudication = decision.get('adjudication')
    final = adjudication or second or initial
    return copy.deepcopy(_verdict_payload(final)), _verdict_trigger_reasons(initial)
```

Import `copy` in the module.

- [ ] **Step 4: Run all Task 2 tests and verify GREEN**

Expected: three tests pass without warnings.

### Task 3: Merge Valid Decisions Into ReviewRecords

**Files:**
- Modify: `schemas/fingoose_macro_review_record_v1.schema.json`
- Modify: `fingoose_macro_event_attribution_v1.py`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`
- Test: `tests/test_fingoose_macro_event_attribution_v1.py`

- [ ] **Step 1: Write failing merge tests**

```python
def test_valid_decision_replaces_pending_record_with_audit_trail(self):
    from fingoose_macro_event_attribution_v1 import apply_review_decision

    base = {
        'review_id': 'review-event-01-single-sp500',
        'dataset_version': 'fingoose-macro-event-attribution-v1.0',
        'event_id': 'event-01',
        'initial_review': {'reviewer_id': 'PENDING_HUMAN', 'status': 'PENDING'},
        'second_review': None,
        'adjudication': None,
        'second_review_trigger_reasons': [],
        'final_label': 'PRIMARY_DRIVER',
        'confidence': 'HIGH',
        'core_dimensions': self._verdict()['core_dimensions'],
    }
    decision = {
        'review_id': base['review_id'],
        'event_id': 'event-01',
        'initial_review': self._verdict(),
        'second_review': None,
        'adjudication': None,
    }
    merged = apply_review_decision(base, decision)
    self.assertEqual(merged['initial_review']['status'], 'APPROVED')
    self.assertEqual(merged['initial_review']['comments'], decision['initial_review']['comments'])
    self.assertEqual(merged['final_label'], 'PRIMARY_DRIVER')
```

- [ ] **Step 2: Run the test and verify RED**

Expected: import error for `apply_review_decision`.

- [ ] **Step 3: Extend ReviewRecord Schema**

Add top-level required property `adjudication`, accepting `null` or `$defs.review`. Extend `$defs.review` with optional `reviewed_at`, `comments`, `label`, `confidence`, and `core_dimensions`. Add an `if/then` rule: when `status` is `APPROVED`, require all five audit/verdict fields.

Update existing approved ReviewRecord fixtures in `tests/test_fingoose_macro_event_attribution_v1.py` to include the timestamp, comments, label, confidence and dimensions. Pending fixtures remain unchanged.

- [ ] **Step 4: Implement the merge**

```python
def _audit_review(verdict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'reviewer_id': verdict['reviewer_id'],
        'status': 'APPROVED',
        'reviewed_at': verdict['reviewed_at'],
        'comments': verdict['comments'],
        **_verdict_payload(verdict),
    }


def apply_review_decision(
    base_review: Mapping[str, Any], decision: Mapping[str, Any],
) -> dict[str, Any]:
    final, trigger_reasons = resolve_review_decision(decision)
    merged = copy.deepcopy(dict(base_review))
    merged['initial_review'] = _audit_review(decision['initial_review'])
    merged['second_review'] = (
        _audit_review(decision['second_review']) if decision.get('second_review') else None
    )
    merged['adjudication'] = (
        _audit_review(decision['adjudication']) if decision.get('adjudication') else None
    )
    merged['second_review_trigger_reasons'] = trigger_reasons
    merged['final_label'] = final['label']
    merged['confidence'] = final['confidence']
    merged['core_dimensions'] = final['core_dimensions']
    return merged
```

Update `_review_record()` so all generated pending records include `'adjudication': None`.

- [ ] **Step 5: Run review Schema and merge tests**

```powershell
python -m unittest tests.test_fingoose_macro_event_attribution_v1 tests.test_fingoose_macro_review_workflow_v1 -v
```

Expected: all tests in both modules pass.

### Task 4: Load Decisions Incrementally And Report Input Errors

**Files:**
- Modify: `build_fingoose_macro_event_attribution_v1.py`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`

- [ ] **Step 1: Write failing loader and incremental-build tests**

Create a test that builds once, writes one valid decision to a project-local test JSONL file, then rebuilds with the new parameter:

```python
def test_one_valid_decision_reduces_initial_pending_count_to_thirty_nine(self):
    from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

    output_root = ROOT / '.test-tmp' / 'macro-review-workflow' / 'incremental'
    decision_path = ROOT / '.test-tmp' / 'macro-review-workflow' / 'one-decision.jsonl'
    decision = {
        'review_id': 'review-event-01-single-sp500',
        'event_id': 'event-01',
        'initial_review': self._verdict(),
        'second_review': None,
        'adjudication': None,
    }
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(decision, ensure_ascii=False) + '\n', encoding='utf-8')
    summary = build_event_attribution_dataset(
        ROOT,
        ROOT / 'configs' / 'fingoose_macro_events_v1.json',
        output_root,
        review_decisions_path=decision_path,
    )
    self.assertEqual(summary['initial_review_pending_count'], 39)
    self.assertFalse(summary['formal_ready'])
```

Add this exact rejection test:

```python
def test_duplicate_unknown_and_event_mismatched_decisions_are_rejected(self):
    from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

    valid = {
        'review_id': 'review-event-01-single-sp500',
        'event_id': 'event-01',
        'initial_review': self._verdict(),
        'second_review': None,
        'adjudication': None,
    }
    duplicate = copy.deepcopy(valid)
    unknown = copy.deepcopy(valid)
    unknown['review_id'] = 'review-event-99-single-missing'
    unknown['event_id'] = 'event-99'
    mismatch = copy.deepcopy(valid)
    mismatch['review_id'] = 'review-event-01-single-vixcls'
    mismatch['event_id'] = 'event-02'
    decision_path = ROOT / '.test-tmp' / 'macro-review-workflow' / 'invalid-decisions.jsonl'
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in [valid, duplicate, unknown, mismatch]),
        encoding='utf-8',
    )
    output_root = ROOT / '.test-tmp' / 'macro-review-workflow' / 'invalid-input'
    build_event_attribution_dataset(
        ROOT,
        ROOT / 'configs' / 'fingoose_macro_events_v1.json',
        output_root,
        review_decisions_path=decision_path,
    )
    codes = {row['code'] for row in read_jsonl(output_root / 'audit_rejections.jsonl')}
    self.assertTrue({
        'REVIEW_DECISION_DUPLICATE',
        'REVIEW_DECISION_UNKNOWN',
        'REVIEW_EVENT_MISMATCH',
    } <= codes)
```

- [ ] **Step 2: Run the tests and verify RED**

Expected: `build_event_attribution_dataset()` rejects the new keyword argument.

- [ ] **Step 3: Implement JSONL loading and indexed validation**

Add:

```python
def _read_review_decisions(path: Path | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path is None or not path.is_file():
        return [], []
    rows = []
    rejections = []
    for line_number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            rejections.append({
                'record_id': f'<review-line-{line_number}>',
                'code': 'REVIEW_DECISION_JSON_INVALID',
                'line_number': line_number,
            })
            continue
        row['_line_number'] = line_number
        rows.append(row)
    return rows, rejections
```

Add `review_decisions_path: Path | None = None` to `build_event_attribution_dataset`. After all base reviews are generated, but before calling `review_errors`, validate duplicate, unknown and event-mismatched IDs. Strip `_line_number` before Schema validation. Apply only error-free decisions with `apply_review_decision`.

Move `review_errors(review)` execution out of the per-event loop and run it only after decision merging. Preserve Schema validation for dossiers, windows and samples.

- [ ] **Step 4: Synchronize final labels back to samples**

After merge, build `review_by_id` and update only label and confidence:

```python
review_by_id = {row['review_id']: row for row in reviews}
for sample in samples:
    review = review_by_id[sample['review_id']]
    sample['attribution']['label'] = review['final_label']
    sample['attribution']['confidence'] = review['confidence']
```

Recalculate `label_counts` after this synchronization.

- [ ] **Step 5: Add CLI input**

```python
parser.add_argument(
    '--review-decisions',
    type=Path,
    default=ROOT / 'configs' / 'fingoose_macro_review_decisions_v1.jsonl',
)
```

Pass `args.review_decisions` into the builder.

- [ ] **Step 6: Run all incremental-import tests and verify GREEN**

Expected: valid rows apply, invalid rows produce exact rejection codes, and missing rows remain pending.

### Task 5: Isolate Public Projection And Produce Hidden Labels

**Files:**
- Modify: `fingoose_macro_event_attribution_v1.py`
- Modify: `build_fingoose_macro_event_attribution_v1.py`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`
- Test: `tests/test_fingoose_macro_event_production_config_v1.py`

- [ ] **Step 1: Write failing visibility tests**

```python
def test_public_projection_removes_attribution_and_review_identity(self):
    from fingoose_macro_event_attribution_v1 import build_public_attribution_projection

    sample = {
        'record_id': 'macro-event-v1-event-01-single-sp500',
        'dataset_version': 'fingoose-macro-event-attribution-v1.0',
        'event_id': 'event-01',
        'task_type': 'single_asset_attribution_forecast',
        'target_series_ids': ['SP500'],
        'as_of_at': '2020-04-07T23:59:59+00:00',
        'forecast_as_of_at': '2020-03-13T23:59:59+00:00',
        'visible_evidence_ids': ['event01-who-pandemic'],
        'market_window_ids': ['event-01-sp500'],
        'attribution': {'label': 'PRIMARY_DRIVER', 'confidence': 'HIGH'},
        'forecast_reasoning_chain': {'short_term_prediction': {'confidence': 'MEDIUM'}},
        'review_id': 'review-event-01-single-sp500',
    }
    projection = build_public_attribution_projection(sample)
    self.assertNotIn('attribution', projection)
    self.assertNotIn('review_id', projection)
    self.assertEqual(
        projection['forecast_reasoning_chain']['short_term_prediction']['confidence'],
        'MEDIUM',
    )
```

Add an integration assertion that `hidden_attribution_labels.jsonl` contains 40 rows with `label_status='PROVISIONAL'` on the default build.

- [ ] **Step 2: Run visibility tests and verify RED**

Expected: import error for `build_public_attribution_projection` and missing hidden-label file.

- [ ] **Step 3: Implement an explicit public whitelist**

```python
PUBLIC_ATTRIBUTION_FIELDS = (
    'record_id', 'dataset_version', 'event_id', 'task_type', 'target_series_ids',
    'as_of_at', 'forecast_as_of_at', 'visible_evidence_ids', 'market_window_ids',
    'forecast_reasoning_chain',
)


def build_public_attribution_projection(sample: Mapping[str, Any]) -> dict[str, Any]:
    projection = {
        key: copy.deepcopy(sample[key])
        for key in PUBLIC_ATTRIBUTION_FIELDS
    }
    assert_public_projection_safe(projection)
    return projection
```

Add `attribution`, `review_id`, `reviewer_id`, `comments`, `initial_review`, `second_review`, and `adjudication` to `HIDDEN_PUBLIC_KEYS`. Do not add `confidence`, because prediction confidence remains a visible input/output contract.

- [ ] **Step 4: Build hidden attribution labels**

```python
def _hidden_attribution_label(
    sample: Mapping[str, Any], review: Mapping[str, Any],
) -> dict[str, Any]:
    release_errors = review_errors(review)
    return {
        'record_id': sample['record_id'],
        'review_id': review['review_id'],
        'hidden_from_model': True,
        'label_status': 'FINAL' if not release_errors else 'PROVISIONAL',
        'label': review['final_label'],
        'confidence': review['confidence'],
        'core_dimensions': copy.deepcopy(review['core_dimensions']),
    }
```

Write 40 rows to `hidden_attribution_labels.jsonl`. Add `hidden_attribution_label_count` and `final_attribution_label_count` to summary. Require 40 final labels in the `formal_ready` expression.

- [ ] **Step 5: Run visibility and production tests**

Expected: public projection contains no attribution or reviewer data, default hidden labels are 40 provisional rows, and production remains blocked only by review gates.

### Task 6: Generate Decision Templates And Blind Second-Review Packets

**Files:**
- Modify: `build_fingoose_macro_event_attribution_v1.py`
- Test: `tests/test_fingoose_macro_review_workflow_v1.py`

- [ ] **Step 1: Write failing artifact tests**

```python
def test_default_build_generates_forty_templates_and_fifteen_blind_second_reviews(self):
    from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

    output_root = ROOT / '.test-tmp' / 'macro-review-workflow' / 'review-materials'
    build_event_attribution_dataset(
        ROOT,
        ROOT / 'configs' / 'fingoose_macro_events_v1.json',
        output_root,
    )
    templates = read_jsonl(output_root / 'review_decision_template.jsonl')
    second_packet = read_jsonl(output_root / 'second_review_packet.jsonl')
    self.assertEqual(len(templates), 40)
    self.assertEqual(len(second_packet), 15)
    serialized = json.dumps(second_packet, ensure_ascii=False, sort_keys=True)
    for forbidden in ('proposed_label', 'proposed_confidence', 'attribution', 'reviewer_id', 'comments'):
        self.assertNotIn(forbidden, serialized)
```

- [ ] **Step 2: Run the test and verify RED**

Expected: both artifact files are missing.

- [ ] **Step 3: Implement the decision template**

Generate one row per work-queue task:

```python
def _review_decision_template(task: Mapping[str, Any]) -> dict[str, Any]:
    empty_verdict = {
        'reviewer_id': '',
        'reviewed_at': '',
        'comments': '',
        'label': None,
        'confidence': None,
        'core_dimensions': {
            'temporal_alignment': None,
            'abnormal_movement': None,
            'transmission_mechanism': None,
            'competing_explanations': None,
        },
    }
    return {
        'review_id': task['review_id'],
        'event_id': task['event_id'],
        'initial_review': copy.deepcopy(empty_verdict),
        'second_review': None,
        'adjudication': None,
    }
```

The template is intentionally not Schema-valid until a human fills every required field.

- [ ] **Step 4: Implement the blind packet**

Build from the existing pilot-style evidence packet, but use only tasks with `second_review_required=True` and `second_review_status!='APPROVED'`. Copy only task identity, event dossier, visible sample fields returned by `build_public_attribution_projection`, market windows and visible sources. Do not copy work-queue proposed labels, initial review objects or hidden outcomes.

- [ ] **Step 5: Run the artifact test and hidden-field scan**

Expected: 40 templates, 15 default blind packets and no forbidden fields.

### Task 7: Prove Complete Reviews Can Open The Gate

**Files:**
- Modify: `tests/test_fingoose_macro_review_workflow_v1.py`
- Modify: `build_fingoose_macro_event_attribution_v1.py`

- [ ] **Step 1: Write a complete-review integration test**

Add this helper and test. It uses each base record's label, confidence and dimensions so the established 10/15/10/5 distribution remains unchanged:

```python
def _decision_from_review(self, review):
    initial = {
        'reviewer_id': 'reviewer-a',
        'reviewed_at': '2026-07-27T10:00:00+08:00',
        'comments': 'All ten review checks were completed against archived evidence.',
        'label': review['final_label'],
        'confidence': review['confidence'],
        'core_dimensions': copy.deepcopy(review['core_dimensions']),
    }
    second = None
    if review['second_review_trigger_reasons']:
        second = copy.deepcopy(initial)
        second['reviewer_id'] = 'reviewer-b'
        second['reviewed_at'] = '2026-07-27T11:00:00+08:00'
        second['comments'] = 'Independent review reached the same verdict.'
    return {
        'review_id': review['review_id'],
        'event_id': review['event_id'],
        'initial_review': initial,
        'second_review': second,
        'adjudication': None,
    }


def test_complete_review_file_opens_all_human_review_gates(self):
    from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

    base_output = ROOT / '.test-tmp' / 'macro-review-workflow' / 'complete-base'
    build_event_attribution_dataset(
        ROOT,
        ROOT / 'configs' / 'fingoose_macro_events_v1.json',
        base_output,
    )
    decisions = [
        self._decision_from_review(row)
        for row in read_jsonl(base_output / 'review_records.jsonl')
    ]
    decision_path = ROOT / '.test-tmp' / 'macro-review-workflow' / 'complete-decisions.jsonl'
    decision_path.write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in decisions),
        encoding='utf-8',
    )
    final_output = ROOT / '.test-tmp' / 'macro-review-workflow' / 'complete-final'
    summary = build_event_attribution_dataset(
        ROOT,
        ROOT / 'configs' / 'fingoose_macro_events_v1.json',
        final_output,
        review_decisions_path=decision_path,
    )
    self.assertTrue(summary['formal_ready'])
    self.assertEqual(summary['initial_review_pending_count'], 0)
    self.assertEqual(summary['second_review_pending_count'], 0)
    self.assertEqual(summary['final_attribution_label_count'], 40)
    self.assertEqual(summary['label_distribution'], {
        'CONTRIBUTING_FACTOR': 15,
        'PRIMARY_DRIVER': 10,
        'UNSUPPORTED': 5,
        'WEAK_RELATION': 10,
    })
```

- [ ] **Step 2: Run the integration test and verify RED**

Expected: `formal_ready` remains false until post-merge review validation and final-label count are correctly integrated.

- [ ] **Step 3: Complete release-gate integration**

Ensure the order inside the builder is:

1. generate dossiers, windows, base samples and base reviews;
2. load and validate review decisions;
3. apply valid decisions;
4. synchronize final labels into internal samples;
5. validate merged ReviewRecords and collect rejections;
6. recalculate label distribution;
7. generate public projection, hidden labels and review materials;
8. compute `formal_ready` from all original gates plus 40 final hidden labels.

No pending-review rejection may be appended before decision merging.

- [ ] **Step 4: Run the complete-review test and verify GREEN**

Expected: complete decisions produce `formal_ready=true`; the unchanged empty production decision file remains `formal_ready=false`.

### Task 8: Update Documentation, Rebuild Production Outputs And Verify

**Files:**
- Modify: `docs/fingoose_macro_event_review_handbook_v1.md`
- Regenerate: `outputs/fingoose_macro_event_attribution_v1/*`
- Test: all macro event tests and full project suite.

- [ ] **Step 1: Document the submission workflow**

Add a section explaining:

1. reviewers read `review_work_queue.jsonl` and the relevant packet;
2. reviewers fill rows from `review_decision_template.jsonl` into `configs/fingoose_macro_review_decisions_v1.jsonl`;
3. second reviewers use only `second_review_packet.jsonl`;
4. reviewers never open `hidden_forecast_outcomes.jsonl` or `hidden_attribution_labels.jsonl`;
5. the builder reports invalid rows with line numbers in `audit_rejections.jsonl`.

- [ ] **Step 2: Run focused verification**

```powershell
python -m unittest `
  tests.test_fingoose_macro_event_attribution_v1 `
  tests.test_build_fingoose_macro_event_attribution_v1 `
  tests.test_fingoose_macro_event_production_config_v1 `
  tests.test_fingoose_macro_projection_v1 `
  tests.test_fingoose_macro_review_workflow_v1 -v
```

Expected: all selected tests pass.

- [ ] **Step 3: Rebuild the production candidate**

```powershell
python build_fingoose_macro_event_attribution_v1.py `
  --config configs/fingoose_macro_events_v1.json `
  --review-decisions configs/fingoose_macro_review_decisions_v1.jsonl `
  --output-root outputs/fingoose_macro_event_attribution_v1
```

Expected exit code: `1`, because the real decision file is empty. Expected summary: `review_preparation_ready=true`, 40 pending initial reviews, 15 pending second reviews, 40 provisional hidden labels, and only review-related release gates.

- [ ] **Step 4: Run the full project suite with project-local temporary storage**

```powershell
$env:TEMP = (Resolve-Path '.test-tmp\full-suite').Path
$env:TMP = $env:TEMP
$env:PYTHONPATH = 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages'
python -m unittest discover -s tests -q
```

Run outside the restricted-token sandbox if Windows denies writes to `TemporaryDirectory` descendants. Expected: zero failures; one existing skipped test is acceptable.

- [ ] **Step 5: Verify production artifact counts and leakage**

Check exactly:

```text
event_dossiers.jsonl                 10
market_windows.jsonl                 40
attribution_samples.jsonl            40
training_projection.jsonl            40
hidden_forecast_outcomes.jsonl       40
hidden_attribution_labels.jsonl      40
review_records.jsonl                 40
review_work_queue.jsonl              40
review_decision_template.jsonl       40
pilot_review_packet.jsonl             8
second_review_packet.jsonl           15
```

Serialize `training_projection.jsonl` and assert it contains none of: `"attribution"`, `"review_id"`, `"reviewer_id"`, `"comments"`, `"actual_direction"`, or `"hidden_forecast_outcome"`.

## Plan Self-Review

- Spec coverage: all design sections map to Tasks 1-8, including incremental import, reviewer independence, adjudication, audit preservation, blind review materials, provisional/final hidden labels, public leakage prevention and release gates.
- Type consistency: all verdicts use `reviewer_id`, `reviewed_at`, `comments`, `label`, `confidence`, and `core_dimensions`; `second_review` and `adjudication` use the same structure.
- Scope: no UI, database, reviewer assignment or causal-estimation work is included.
- Verification: every production behavior begins with a failing test and ends with focused plus full-suite validation.
