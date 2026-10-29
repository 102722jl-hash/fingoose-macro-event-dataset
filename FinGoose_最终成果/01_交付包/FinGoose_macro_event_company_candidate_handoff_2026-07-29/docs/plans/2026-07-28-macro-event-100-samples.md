# FinGoose Event Macro 100-Sample Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate 100-record event-driven macro research-candidate set from the existing ten verified event configurations, with public transmission summaries and isolated D20 outcomes.

**Architecture:** Leave the 40-record `fingoose_macro_event_attribution_v1` workflow unchanged. A focused v1.1 candidate module reads its configuration and archived market windows, generates ten semantically distinct records per event, produces Chinese public commentaries, and validates source integrity, time isolation, per-event quotas, uniqueness, and commentary constraints before writing an independent output directory.

**Tech Stack:** Python 3.12 standard library, existing `fingoose_macro_event_attribution_v1` date/window utilities, JSON/JSONL, `unittest`.

---

## File Structure

- Create: `fingoose_macro_event_100_candidate_v1.py`
  - Defines the new record contract, variation generator, public-commentary builder, and pure validator.
- Create: `build_fingoose_macro_event_100_candidate_v1.py`
  - Reads existing event configuration and local snapshots, constructs the 100-record output, and writes the audit artefacts.
- Create: `schemas/fingoose_macro_event_100_candidate_v1.schema.json`
  - Strict JSON Schema for visible candidate records.
- Create: `tests/test_fingoose_macro_event_100_candidate_v1.py`
  - Unit and integration tests for quotas, source integrity, public summaries, and hidden-result isolation.
- Create: `outputs/fingoose_macro_event_attribution_v1_100/`
  - Generated candidates and audit files. This directory is derived output, not a source of truth.

## Record Model

Each of the ten events emits these ten non-duplicate records:

| `sample_kind` | Count | Purpose |
| --- | ---: | --- |
| `single_target` | 4 | One record for every configured target series. |
| `cross_asset` | 2 | Tests one global and one China-linked pair of series. |
| `channel_check` | 2 | Evaluates a distinct configured transmission channel against a target. |
| `counterfactual` | 2 | Tests a documented competing explanation; conclusion may be `UNCERTAIN`. |

Each candidate contains only evidence visible at its `forecast_as_of_at`, a D3 period comparison, at least two supporting observations, one documented counterevidence item, a structured transmission chain, a D20 short-horizon prediction, and a 150-300 Chinese-character `final_commentary`. D20 observations and actual labels exist only in `hidden_outcomes.jsonl`.

### Task 1: Define the 100-sample contract and write red tests

**Files:**
- Create: `schemas/fingoose_macro_event_100_candidate_v1.schema.json`
- Create: `tests/test_fingoose_macro_event_100_candidate_v1.py`

- [ ] **Step 1: Add a minimal valid-record fixture and quota test.**

```python
def test_validate_candidate_requires_two_supporting_observations_and_a_counterevidence_item(self):
    from fingoose_macro_event_100_candidate_v1 import validate_candidate_record

    record = self._valid_record()
    record['supporting_observations'] = record['supporting_observations'][:1]
    record['counterevidence'] = []

    errors = validate_candidate_record(record, self._manifest())

    self.assertIn('SUPPORTING_OBSERVATIONS_INSUFFICIENT', errors)
    self.assertIn('COUNTEREVIDENCE_REQUIRED', errors)
```

- [ ] **Step 2: Run the focused test and verify the expected red state.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1.MacroEvent100CandidateTests.test_validate_candidate_requires_two_supporting_observations_and_a_counterevidence_item -v
```

Expected: failure because `fingoose_macro_event_100_candidate_v1` does not exist.

- [ ] **Step 3: Add the strict JSON Schema.**

Require the following top-level fields and set `additionalProperties` to `false`:

```json
{
  "required": [
    "record_id", "dataset_version", "event_id", "sample_kind", "target_series_ids",
    "forecast_as_of_at", "visible_evidence_ids", "period_comparison",
    "fact_transmission_chain", "supporting_observations", "counterevidence",
    "short_horizon_prediction", "final_commentary", "review_status"
  ],
  "properties": {
    "dataset_version": {"const": "fingoose-macro-event-100-candidate-v1.0"},
    "sample_kind": {"enum": ["single_target", "cross_asset", "channel_check", "counterfactual"]},
    "review_status": {"const": "PENDING_HUMAN_REVIEW"}
  }
}
```

Make `supporting_observations` require two items, `counterevidence` require one item, and `final_commentary` require a string.

- [ ] **Step 4: Implement the minimum pure validator in `fingoose_macro_event_100_candidate_v1.py`.**

```python
def validate_candidate_record(record: Mapping[str, Any], manifest: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(record.get('supporting_observations', [])) < 2:
        errors.append('SUPPORTING_OBSERVATIONS_INSUFFICIENT')
    if not record.get('counterevidence'):
        errors.append('COUNTEREVIDENCE_REQUIRED')
    if record.get('review_status') != 'PENDING_HUMAN_REVIEW':
        errors.append('REVIEW_STATUS_INVALID')
    return errors
```

- [ ] **Step 5: Re-run the focused test.**

Run the command in Step 2. Expected: `OK`.

### Task 2: Build deterministic ten-variation event records

**Files:**
- Create: `fingoose_macro_event_100_candidate_v1.py`
- Test: `tests/test_fingoose_macro_event_100_candidate_v1.py`

- [ ] **Step 1: Add an integration test for the exact 10-per-event profile.**

```python
def test_build_event_variations_emits_four_single_two_cross_two_channel_two_counterfactual(self):
    from fingoose_macro_event_100_candidate_v1 import build_event_variations

    records = build_event_variations(self._event(), self._windows())

    self.assertEqual(len(records), 10)
    self.assertEqual(Counter(row['sample_kind'] for row in records), {
        'single_target': 4,
        'cross_asset': 2,
        'channel_check': 2,
        'counterfactual': 2,
    })
    self.assertEqual(len({row['semantic_fingerprint'] for row in records}), 10)
```

- [ ] **Step 2: Run the integration test and verify the expected red state.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1.MacroEvent100CandidateTests.test_build_event_variations_emits_four_single_two_cross_two_channel_two_counterfactual -v
```

Expected: failure because `build_event_variations` does not exist.

- [ ] **Step 3: Implement `build_event_variations(event, windows)`.**

Use the four configured targets in their stable configuration order. Emit:

```python
variation_specs = [
    ('single_target', [targets[0]], targets[0], targets[0]['attribution']),
    ('single_target', [targets[1]], targets[1], targets[1]['attribution']),
    ('single_target', [targets[2]], targets[2], targets[2]['attribution']),
    ('single_target', [targets[3]], targets[3], targets[3]['attribution']),
    ('cross_asset', [targets[0], targets[1]], targets[0], event['cross_asset_attribution']),
    ('cross_asset', [targets[2], targets[3]], targets[2], event['cross_asset_attribution']),
    ('channel_check', [targets[0], targets[3]], targets[0], targets[0]['attribution']),
    ('channel_check', [targets[1], targets[2]], targets[1], targets[1]['attribution']),
    ('counterfactual', [targets[2]], targets[2], targets[2]['attribution']),
    ('counterfactual', [targets[3]], targets[3], targets[3]['attribution']),
]
```

For the final two records set `prediction.direction` to `UNCERTAIN`; preserve the target's documented counterevidence as the central competing explanation. Build the visible period from D1/D3 only, use D20 only later in the hidden outcome builder, and create `semantic_fingerprint` from event ID, kind, target IDs, selected channel, and counterevidence text using SHA-256.

- [ ] **Step 4: Re-run the integration test.**

Run the command in Step 2. Expected: `OK`.

### Task 3: Add public Chinese short commentaries and hidden-result isolation

**Files:**
- Modify: `fingoose_macro_event_100_candidate_v1.py`
- Test: `tests/test_fingoose_macro_event_100_candidate_v1.py`

- [ ] **Step 1: Write failing tests for commentary bounds and hidden leakage.**

```python
def test_commentary_is_chinese_public_summary_without_hidden_outcome(self):
    from fingoose_macro_event_100_candidate_v1 import build_final_commentary, validate_candidate_record

    commentary = build_final_commentary(self._event(), self._valid_record())
    record = self._valid_record()
    record['final_commentary'] = commentary

    self.assertGreaterEqual(len(commentary), 150)
    self.assertLessEqual(len(commentary), 300)
    self.assertNotIn('D20', commentary)
    self.assertNotIn('actual_direction', commentary)
    self.assertEqual(validate_candidate_record(record, self._manifest()), [])
```

- [ ] **Step 2: Run the commentary test and verify red.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1.MacroEvent100CandidateTests.test_commentary_is_chinese_public_summary_without_hidden_outcome -v
```

Expected: failure because `build_final_commentary` does not exist.

- [ ] **Step 3: Implement a deterministic public-summary builder and isolation checks.**

`build_final_commentary()` must concatenate five short Chinese clauses: event background, two D3 observations, the documented channel, the counterevidence limitation, and the stated short-horizon prediction. It must derive all observations from the record's D1/D3 fields. Pad with a fixed, meaningful evidence-limitation sentence only when needed; never pad with repeated text. Add these checks to `validate_candidate_record()`:

```python
serialized = json.dumps(record, ensure_ascii=True, sort_keys=True).lower()
if any(token in serialized for token in ('actual_direction', 'verification_status', 'outcome_window', 'd20')):
    errors.append('HIDDEN_OUTCOME_LEAKAGE')
if not 150 <= len(str(record.get('final_commentary', ''))) <= 300:
    errors.append('COMMENTARY_LENGTH_INVALID')
if not _contains_cjk(str(record.get('final_commentary', ''))):
    errors.append('COMMENTARY_CHINESE_REQUIRED')
```

Keep D20 values in a separate `build_hidden_outcome(record, windows)` return value; the public candidate may retain only its forecast horizon label `SHORT_HORIZON`.

- [ ] **Step 4: Re-run the commentary test.**

Run the command in Step 2. Expected: `OK`.

### Task 4: Implement source/time/uniqueness validation and the CLI builder

**Files:**
- Create: `build_fingoose_macro_event_100_candidate_v1.py`
- Modify: `fingoose_macro_event_100_candidate_v1.py`
- Test: `tests/test_fingoose_macro_event_100_candidate_v1.py`

- [ ] **Step 1: Write the failing end-to-end build test.**

```python
def test_build_dataset_writes_one_hundred_pending_candidates_and_isolated_outcomes(self):
    from build_fingoose_macro_event_100_candidate_v1 import build_macro_event_100_dataset

    with tempfile.TemporaryDirectory() as directory:
        report = build_macro_event_100_dataset(ROOT, ROOT / 'configs' / 'fingoose_macro_events_v1.json', Path(directory))
        rows = self._read_jsonl(Path(directory) / 'macro_candidates.jsonl')
        hidden = self._read_jsonl(Path(directory) / 'hidden_outcomes.jsonl')

    self.assertEqual((report['event_count'], report['sample_count']), (10, 100))
    self.assertEqual(len(hidden), 100)
    self.assertTrue(all(row['review_status'] == 'PENDING_HUMAN_REVIEW' for row in rows))
    self.assertNotIn('actual_direction', json.dumps(rows, ensure_ascii=True))
```

- [ ] **Step 2: Run the end-to-end test and verify red.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1.MacroEvent100CandidateTests.test_build_dataset_writes_one_hundred_pending_candidates_and_isolated_outcomes -v
```

Expected: failure because the builder module does not exist.

- [ ] **Step 3: Implement `build_macro_event_100_dataset`.**

For every event:

1. Verify each source snapshot file exists and its SHA-256 equals `content_sha256`.
2. Reuse `_market_window()` from `build_fingoose_macro_event_attribution_v1.py` to compute four windows.
3. Use `build_event_variations()` to produce ten candidates and `build_hidden_outcome()` for their isolated outcomes.
4. Reject a record when its event source or macro-report time is after `forecast_as_of_at`, a snapshot hash differs, a target window lacks D1/D3/D20, or a semantic fingerprint is repeated.

Write these files:

```text
<output-root>/macro_candidates.jsonl
<output-root>/hidden_outcomes.jsonl
<output-root>/review_queue.jsonl
<output-root>/source_manifest.jsonl
<output-root>/rejected.jsonl
<output-root>/summary.json
```

The `summary.json` must contain `event_count`, `sample_count`, `samples_per_event`, `review_status`, `rejected_count`, `ready_for_human_review`, and the fixed distribution. `ready_for_human_review` is true only when there are exactly 100 candidates, 100 hidden outcomes, no hard rejections, and every record remains `PENDING_HUMAN_REVIEW`.

- [ ] **Step 4: Re-run the end-to-end test.**

Run the command in Step 2. Expected: `OK`.

### Task 5: Add tamper regression tests and generate the candidate set

**Files:**
- Modify: `tests/test_fingoose_macro_event_100_candidate_v1.py`
- Generate: `outputs/fingoose_macro_event_attribution_v1_100/*`

- [ ] **Step 1: Add regression tests for a tampered source, future evidence, duplicate fingerprint, and hidden injection.**

```python
def test_validator_rejects_tampered_or_future_or_hidden_candidate(self):
    from fingoose_macro_event_100_candidate_v1 import validate_candidate_record

    record = self._valid_record()
    record['forecast_as_of_at'] = '2020-03-10T23:59:59+00:00'
    record['visible_evidence_ids'] = ['unknown-source']
    record['final_commentary'] += ' actual_direction=UP'

    errors = validate_candidate_record(record, self._manifest())

    self.assertIn('UNKNOWN_VISIBLE_EVIDENCE', errors)
    self.assertIn('FUTURE_VISIBLE_EVIDENCE', errors)
    self.assertIn('HIDDEN_OUTCOME_LEAKAGE', errors)
```

- [ ] **Step 2: Run the new regression test and verify red, then implement its checks.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1.MacroEvent100CandidateTests.test_validator_rejects_tampered_or_future_or_hidden_candidate -v
```

Expected: failure until `validate_candidate_record()` checks evidence existence, source publication time, and forbidden hidden tokens.

Implement by resolving every `visible_evidence_id` in the manifest, parsing source `published_at` with `datetime.fromisoformat`, and comparing timezone-aware values.

- [ ] **Step 3: Run the complete focused test module.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_100_candidate_v1 -v
```

Expected: all tests pass.

- [ ] **Step 4: Run existing macro regressions.**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_attribution_v1 tests.test_build_fingoose_macro_event_attribution_v1 tests.test_fingoose_macro_event_production_config_v1 -v
```

Expected: all tests pass; the old production profile remains 40 samples.

- [ ] **Step 5: Generate and inspect the independent 100-record output.**

Run:

```powershell
python build_fingoose_macro_event_100_candidate_v1.py --root . --output-root outputs/fingoose_macro_event_attribution_v1_100
```

Expected: JSON summary with `event_count: 10`, `sample_count: 100`, `samples_per_event: 10`, `rejected_count: 0`, and `ready_for_human_review: true`.

## Plan Self-Review

- The plan preserves the existing 40-record candidate workflow and v0.2 Canonical artefacts, while its new module implements all 100-record requirements from the approved design.
- Task 1 covers the strict visible record contract; Task 2 fixes the exact 10-per-event distribution and semantic de-duplication; Task 3 covers the 150-300-character public short commentary and D20 isolation; Task 4 covers source hashes, timezone checks and output files; Task 5 covers tamper behavior and regressions.
- The plan contains no placeholders. All generated output remains research-candidate material with mandatory human review; no step enables a formal training release.
