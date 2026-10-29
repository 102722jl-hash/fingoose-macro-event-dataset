# FinGoose Unified Multi-Task SFT Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible training module that joins the ten FinGoose macro events with 77 industry mappings, 30 company mappings, and 40 event-linked Q&A records, then emits validated `messages` SFT samples and exposes a 3B QLoRA training entry point for an RTX 4060 Laptop 8GB GPU.

**Architecture:** Existing `data/` and `work/` packages remain read-only sources. A pure-Python data layer creates an event-centered `unified_events.jsonl`, projects it into one `sft_dataset.jsonl` with an event-level split field, validates lineage and leakage gates, and only then permits the optional Transformers/TRL/PEFT training layer to start.

**Tech Stack:** Python 3.12 standard library for data construction, pytest for tests, Hugging Face Datasets/Transformers, TRL, PEFT, Accelerate, PyTorch, and bitsandbytes for GPU training.

---

## Version Control Note

The current workspace contains no valid Git repository (`git rev-parse` fails), so this plan does not initialize Git or include executable commit steps. If the project is later placed in a valid repository, each task below is an appropriate commit boundary.

## File Map

- `training/configs/dataset.json`: source paths, explicit event split, enabled tasks, output paths.
- `training/configs/sft_qlora_3b.json`: supported 8GB VRAM baseline.
- `training/configs/sft_qlora_7b_experimental.json`: explicitly non-baseline 7B configuration.
- `training/fingoose_training/loaders.py`: strict JSON/JSONL reads and source-bundle loading.
- `training/fingoose_training/splits.py`: explicit event-level split assignment and leakage checks.
- `training/fingoose_training/unified_builder.py`: event-centered joins and lineage.
- `training/fingoose_training/sft_projector.py`: deterministic Chinese `messages` projection.
- `training/fingoose_training/validation.py`: structural, referential, temporal, and hidden-label gates.
- `training/fingoose_training/metrics.py`: rule-based domain evaluation summaries.
- `training/scripts/*.py`: thin command-line entry points.
- `training/data/*`: generated datasets and audit reports.
- `training/runs/*`: generated adapters and run-specific metrics.

### Task 1: Scaffold Package and Config Contracts

**Files:**
- Create: `training/README.md`
- Create: `training/requirements.txt`
- Create: `training/.gitignore`
- Create: `training/configs/dataset.json`
- Create: `training/configs/sft_qlora_3b.json`
- Create: `training/configs/sft_qlora_7b_experimental.json`
- Create: `training/fingoose_training/__init__.py`
- Create: `training/tests/test_configs.py`

- [ ] **Step 1: Write the failing configuration test**

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_config_declares_all_sources_and_disjoint_event_splits():
    config = json.loads((ROOT / "configs" / "dataset.json").read_text(encoding="utf-8"))
    assert set(config["sources"]) == {"macro", "industry", "company", "qa"}
    split_sets = [set(values) for values in config["splits"].values()]
    assert set.union(*split_sets) == {f"event-{index:02d}" for index in range(1, 11)}
    assert all(left.isdisjoint(right) for index, left in enumerate(split_sets) for right in split_sets[index + 1 :])


def test_3b_config_is_the_supported_low_memory_baseline():
    config = json.loads((ROOT / "configs" / "sft_qlora_3b.json").read_text(encoding="utf-8"))
    assert config["quantization"]["load_in_4bit"] is True
    assert config["training"]["max_seq_length"] == 2048
    assert config["training"]["per_device_train_batch_size"] == 1
    assert config["training"]["gradient_checkpointing"] is True
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest training/tests/test_configs.py -q`

Expected: FAIL because the `training/configs` files do not exist.

- [ ] **Step 3: Create minimal package metadata and configurations**

Use explicit source-file lists in `dataset.json`; do not glob arbitrary candidate files. Fix the split to `event-01` through `event-08` for train, `event-09` for validation, and `event-10` for test. Set `dataset_version` to `fingoose-unified-sft-v1` and enable all four task types.

The 3B config must declare 4-bit NF4, double quantization, bfloat16 compute, sequence length 2048, batch size 1, gradient accumulation 16, gradient checkpointing, three epochs, and adapter-only saves. The 7B config must carry `experimental=true` and must not be selected by default.

- [ ] **Step 4: Run the test and verify GREEN**

Run: `python -m pytest training/tests/test_configs.py -q`

Expected: `2 passed`.

### Task 2: Strict JSONL Loaders

**Files:**
- Create: `training/fingoose_training/loaders.py`
- Create: `training/tests/test_loaders.py`

- [ ] **Step 1: Write failing loader tests**

```python
import json
from pathlib import Path

import pytest

from fingoose_training.loaders import JsonlError, read_json, read_jsonl


def test_read_jsonl_reports_path_and_line_for_bad_json(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"event_id":"event-01"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(JsonlError, match=r"bad\.jsonl:2"):
        read_jsonl(path)


def test_read_jsonl_rejects_duplicate_stable_ids(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    row = {"event_id": "event-01", "case_id": "qa-1"}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JsonlError, match="duplicate case_id"):
        read_jsonl(path, unique_key="case_id")


def test_read_json_requires_an_object(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        read_json(path)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_loaders.py -q`

Expected: FAIL because `fingoose_training.loaders` does not exist.

- [ ] **Step 3: Implement the minimal loader API**

```python
class JsonlError(ValueError):
    pass


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def read_jsonl(path: Path, unique_key: str | None = None) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise JsonlError(f"{path}:{line_number}: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise JsonlError(f"{path}:{line_number}: expected JSON object")
            if unique_key and row.get(unique_key) in seen:
                raise JsonlError(f"{path}:{line_number}: duplicate {unique_key}={row.get(unique_key)}")
            if unique_key:
                seen.add(row.get(unique_key))
            rows.append(row)
    return rows
```

Add `load_source_bundle(project_root, config)` that reads only the configured macro, industry, company, and Q&A files and returns a dictionary keyed by logical dataset name. Do not read `evaluator_only/` or `hidden/` paths.

- [ ] **Step 4: Run loader tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_loaders.py -q`

Expected: `3 passed`.

### Task 3: Event-Level Split Contract

**Files:**
- Create: `training/fingoose_training/splits.py`
- Create: `training/tests/test_splits.py`

- [ ] **Step 1: Write failing split tests**

```python
import pytest

from fingoose_training.splits import SplitError, build_event_split_index, tag_samples


def test_build_event_split_index_rejects_overlap():
    with pytest.raises(SplitError, match="appears in both"):
        build_event_split_index({"train": ["event-01"], "test": ["event-01"]})


def test_tag_samples_keeps_every_sample_for_an_event_together():
    samples = [
        {"sample_id": "a", "event_id": "event-01"},
        {"sample_id": "b", "event_id": "event-01"},
        {"sample_id": "c", "event_id": "event-10"},
    ]
    tagged = tag_samples(samples, {"train": ["event-01"], "test": ["event-10"]})
    assert [row["split"] for row in tagged] == ["train", "train", "test"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_splits.py -q`

Expected: FAIL because `fingoose_training.splits` does not exist.

- [ ] **Step 3: Implement explicit split indexing**

Implement `build_event_split_index(splits) -> dict[str, str]`, rejecting duplicate event membership and unsupported split names. Implement `tag_samples(samples, splits)` as a non-mutating transformation that rejects any event missing from the manifest.

- [ ] **Step 4: Run split tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_splits.py -q`

Expected: `2 passed`.

### Task 4: Build the Unified Event Records

**Files:**
- Create: `training/fingoose_training/unified_builder.py`
- Create: `training/tests/test_unified_builder.py`

- [ ] **Step 1: Write a failing event-join test with real source key names**

```python
from fingoose_training.unified_builder import BuildError, build_unified_events


def test_build_unified_event_nests_industry_company_and_qa():
    source = {
        "event_episodes": [{"event_id": "event-01", "episode_id": "ep-1", "phase": "SHOCK"}],
        "event_milestones": [{"event_id": "event-01", "milestone_id": "m-1", "fact": "事件事实"}],
        "transmission_graphs": [{"event_id": "event-01", "graph_id": "g-1", "nodes": [], "edges": []}],
        "macro_market_windows": [{"event_id": "event-01", "market_window_id": "mw-1", "windows": {}}],
        "event_industry_mappings": [{"event_id": "event-01", "event_industry_mapping_id": "ei-1", "display_name_zh": "航空"}],
        "industry_mechanism_chains": [{"event_id": "event-01", "event_industry_mapping_id": "ei-1", "nodes": []}],
        "industry_market_windows": [{"event_id": "event-01", "event_industry_mapping_id": "ei-1", "fixed_windows": {}}],
        "industry_evidence": [],
        "event_company_map": [{"event_id": "event-01", "mapping_id": "ec-1", "company_code": "600009.SH", "industry_impact_id": "ei-1"}],
        "company_mechanism_chains": [{"event_id": "event-01", "mapping_id": "ec-1", "nodes": []}],
        "direction_assessments": [{"event_id": "event-01", "mapping_id": "ec-1", "company_code": "600009.SH", "horizons": {}}],
        "company_evidence": [],
        "company_market_windows": [],
        "company_confounders": [],
        "company_counterevidence_reviews": [],
        "qa_cases": [{"event_id": "event-01", "case_id": "qa-1", "question_zh": "如何影响？"}],
        "qa_answers": [{"event_id": "event-01", "case_id": "qa-1", "task_answer": {"direct_answer_zh": "影响说明"}}],
    }
    records = build_unified_events(source, dataset_version="fingoose-unified-sft-v1")
    assert len(records) == 1
    assert records[0]["industries"][0]["event_industry_mapping_id"] == "ei-1"
    assert records[0]["companies"][0]["mapping_id"] == "ec-1"
    assert records[0]["qa"][0]["case_id"] == "qa-1"
```

Add tests that a missing Q&A answer, conflicting event IDs for the same `case_id`, and a company mechanism chain with an unknown `mapping_id` raise `BuildError`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_unified_builder.py -q`

Expected: FAIL because `build_unified_events` is missing.

- [ ] **Step 3: Implement deterministic event-centered joins**

Create helpers equivalent to:

```python
def index_unique(rows: list[dict], key: str, label: str) -> dict[str, dict]: ...
def group_by(rows: list[dict], key: str) -> dict[str, list[dict]]: ...
def build_unified_events(source: dict[str, list[dict]], dataset_version: str) -> list[dict]: ...
```

Use `event_id` to group macro records, `event_industry_mapping_id` for industry detail joins, `mapping_id` for company detail joins, and `case_id` for Q&A joins. Preserve the full candidate records under stable named subobjects rather than copying selected values and losing lineage. Sort events, industries, companies, and questions by stable IDs for deterministic output.

Resolve `event_title_zh` from Q&A cases first, then industry mappings. Emit `lineage.source_record_ids` from milestone IDs, mapping IDs, company mapping IDs, and case IDs. Never read hidden labels.

- [ ] **Step 4: Run builder tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_unified_builder.py -q`

Expected: all builder tests pass.

### Task 5: Project Unified Records to Standard SFT Messages

**Files:**
- Create: `training/fingoose_training/sft_projector.py`
- Create: `training/tests/test_sft_projector.py`

- [ ] **Step 1: Write failing projector tests**

```python
from fingoose_training.sft_projector import project_sft_samples


def test_projector_emits_four_task_types_for_one_complete_event(complete_event):
    samples = project_sft_samples([complete_event])
    assert {sample["task_type"] for sample in samples} == {
        "EVENT_ANALYSIS", "INDUSTRY_IMPACT", "COMPANY_IMPACT", "EVENT_QA"
    }
    for sample in samples:
        assert sample["event_id"] == "event-01"
        assert [message["role"] for message in sample["messages"]] == ["system", "user", "assistant"]
        assert all(message["content"].strip() for message in sample["messages"])


def test_qa_answer_uses_candidate_direct_answer_not_hidden_labels(complete_event):
    sample = next(row for row in project_sft_samples([complete_event]) if row["task_type"] == "EVENT_QA")
    assert "候选直接答案" in sample["messages"][2]["content"]
    assert "hidden" not in sample["messages"][2]["content"].lower()
```

- [ ] **Step 2: Run projector tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_sft_projector.py -q`

Expected: FAIL because the projector does not exist.

- [ ] **Step 3: Implement deterministic Chinese renderers**

Implement one renderer per task type. `system` states evidence and uncertainty rules. `user` contains a compact Chinese presentation of only the relevant event, industry, company, market, and evidence fields. `assistant` is rendered from existing candidate conclusions:

- EVENT_ANALYSIS: milestones, graph, observable windows, and stated uncertainty.
- INDUSTRY_IMPACT: mapping fields, mechanism-chain nodes, horizons, counterevidence, and invalidation conditions.
- COMPANY_IMPACT: direction assessment, mechanism chain, company evidence, confounders, counterevidence, and horizons.
- EVENT_QA: `task_answer.direct_answer_zh` plus existing source facts, calculated facts, research inferences, refusal boundaries, and horizon reasoning.

Use `json.dumps(..., ensure_ascii=False, sort_keys=True)` for structured prompt sections. Do not invent prose beyond fixed connective labels. Generate stable sample IDs from task type and existing stable IDs.

- [ ] **Step 4: Run projector tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_sft_projector.py -q`

Expected: all projector tests pass.

### Task 6: Validate Data, Lineage, and Leakage Gates

**Files:**
- Create: `training/fingoose_training/validation.py`
- Create: `training/tests/test_validation.py`

- [ ] **Step 1: Write failing gate tests**

```python
from fingoose_training.validation import validate_datasets


def test_validation_rejects_cross_split_event(valid_unified, valid_samples):
    valid_samples[0]["split"] = "train"
    valid_samples[1]["event_id"] = valid_samples[0]["event_id"]
    valid_samples[1]["split"] = "test"
    report = validate_datasets(valid_unified, valid_samples, expected_events={"event-01"})
    assert report["valid"] is False
    assert "EVENT_SPLIT_LEAKAGE" in {error["code"] for error in report["errors"]}


def test_validation_rejects_nonstandard_message_roles(valid_unified, valid_samples):
    valid_samples[0]["messages"][2]["role"] = "model"
    report = validate_datasets(valid_unified, valid_samples, expected_events={"event-01"})
    assert "INVALID_MESSAGE_ROLES" in {error["code"] for error in report["errors"]}
```

Add checks for missing event coverage, duplicate sample IDs, empty assistant content, unresolved company/industry references, `evaluator_only`/`hidden` lineage paths, and forbidden hidden-label field names.

- [ ] **Step 2: Run validation tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_validation.py -q`

Expected: FAIL because `validate_datasets` does not exist.

- [ ] **Step 3: Implement structured validation reports**

Return a JSON-serializable report with `valid`, `errors`, `warnings`, `counts`, `task_counts`, `event_counts`, and `split_counts`. Every error must include a stable code, human-readable Chinese message, and relevant record ID. Validation must not silently repair invalid data.

- [ ] **Step 4: Run validation tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_validation.py -q`

Expected: all validation tests pass.

### Task 7: Add Deterministic Build and Validation CLIs

**Files:**
- Create: `training/scripts/build_unified_dataset.py`
- Create: `training/scripts/build_sft_dataset.py`
- Create: `training/scripts/validate_dataset.py`
- Create: `training/tests/test_build_cli.py`

- [ ] **Step 1: Write a failing end-to-end CLI test**

Create a temporary source tree with one complete event, invoke the three script `main(argv)` functions, and assert that they write UTF-8 JSONL, `split_manifest.json`, `manifest.json`, and a valid validation report. Run the build twice and assert identical dataset bytes and hashes, excluding the report generation timestamp.

- [ ] **Step 2: Run the CLI test and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_build_cli.py -q`

Expected: FAIL because the CLI scripts do not exist.

- [ ] **Step 3: Implement thin CLI entry points**

Each script must accept `--config` and resolve relative paths against the project root declared by the config location. Use temporary files followed by `Path.replace` for complete-file writes. `build_sft_dataset.py` must write a canonical event split manifest and tag every generated sample. `validate_dataset.py` must return exit code 1 when `valid=false`.

`manifest.json` must include dataset version, source file paths, source and output SHA-256 values, record counts, task counts, event counts, and split counts.

- [ ] **Step 4: Run CLI tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_build_cli.py -q`

Expected: all CLI tests pass.

### Task 8: Add Metrics and QLoRA Training Entry

**Files:**
- Create: `training/fingoose_training/metrics.py`
- Create: `training/scripts/train_sft.py`
- Create: `training/scripts/evaluate_sft.py`
- Create: `training/tests/test_metrics.py`
- Create: `training/tests/test_training_cli.py`

- [ ] **Step 1: Write failing metric and dry-run tests**

```python
from fingoose_training.metrics import evaluate_predictions


def test_metrics_group_results_by_task_and_event():
    rows = [{"event_id": "event-01", "task_type": "EVENT_QA", "metadata": {"evidence_ids": ["e-1"]}}]
    predictions = [{"text": "依据证据 e-1，即时影响与短期影响不同；中期仍不确定。"}]
    report = evaluate_predictions(rows, predictions)
    assert report["sample_count"] == 1
    assert report["by_task"]["EVENT_QA"]["sample_count"] == 1
    assert report["evidence_reference_valid_rate"] == 1.0
```

The training CLI test must invoke `main(["--config", ..., "--dry-run"])` with a valid tiny SFT dataset and assert it checks configuration, split presence, message roles, and output directory without importing or downloading a model.

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_metrics.py training/tests/test_training_cli.py -q`

Expected: FAIL because metrics and training entry points are missing.

- [ ] **Step 3: Implement rule-based metrics and lazy training imports**

`metrics.py` reports format compliance, evidence-ID reference validity, horizon-term coverage, uncertainty-language coverage, and per-event/per-task counts. It must label these as compliance metrics, not semantic correctness or causal proof.

`train_sft.py` must:

1. Load and validate the config and SFT dataset.
2. Refuse to train if `validation_report.json` is invalid or does not match dataset hashes.
3. Filter `split=train` and `split=validation`.
4. On `--dry-run`, print a JSON readiness report and exit without importing heavy libraries.
5. Otherwise lazily import torch, datasets, transformers, trl, peft, and bitsandbytes.
6. Load the configured model in 4-bit, prepare LoRA, use the tokenizer chat template, mask non-assistant tokens where supported, and save only adapter artifacts.
7. Write the resolved training config, dataset manifest, and train metrics under a unique run ID.

`evaluate_sft.py` loads the adapter and test split only when explicitly invoked; it writes predictions separately from `evaluation_metrics.json` and never adds predictions back to the source dataset.

- [ ] **Step 4: Run metric and training CLI tests and verify GREEN**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests/test_metrics.py training/tests/test_training_cli.py -q`

Expected: all tests pass without requiring model downloads.

### Task 9: Build the Real Ten-Event Dataset and Document Operation

**Files:**
- Modify: `training/README.md`
- Generate: `training/data/unified_events.jsonl`
- Generate: `training/data/sft_dataset.jsonl`
- Generate: `training/data/split_manifest.json`
- Generate: `training/data/manifest.json`
- Generate: `training/data/validation_report.json`

- [ ] **Step 1: Run all data-layer tests before real generation**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests -q`

Expected: all tests pass.

- [ ] **Step 2: Generate unified event records**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python training/scripts/build_unified_dataset.py --config training/configs/dataset.json`

Expected: `unified_events.jsonl` contains 10 event records.

- [ ] **Step 3: Generate tagged SFT samples**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python training/scripts/build_sft_dataset.py --config training/configs/dataset.json`

Expected baseline from current sources: 10 EVENT_ANALYSIS, 77 INDUSTRY_IMPACT, 30 COMPANY_IMPACT, and 40 EVENT_QA samples, for 157 total unless a source record is rejected by a documented gate.

- [ ] **Step 4: Validate the generated datasets**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python training/scripts/validate_dataset.py --config training/configs/dataset.json`

Expected: exit 0 and `validation_report.json` has `valid=true`, ten covered events, four task types, and zero split leakage errors.

- [ ] **Step 5: Run the supported training dry-run**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run`

Expected: readiness JSON reports valid dataset, train and validation sample counts, 4-bit configuration, and no model download.

- [ ] **Step 6: Complete README instructions**

Document Windows PowerShell commands, NVIDIA/CUDA prerequisites, dependency installation, build/validate/dry-run/train/evaluate flow, output locations, 8GB VRAM expectations, 7B experimental warning, and the rule that `unified_events.jsonl` is the research master while `sft_dataset.jsonl` is generated training data.

### Task 10: Final Verification

**Files:**
- Verify all files under `training/`

- [ ] **Step 1: Run the full training-module test suite**

Run: `$env:PYTHONPATH=(Resolve-Path 'training').Path; python -m pytest training/tests -q`

Expected: zero failures.

- [ ] **Step 2: Compile all Python files**

Run: `python -m compileall -q training/fingoose_training training/scripts`

Expected: exit 0 with no syntax errors.

- [ ] **Step 3: Rebuild and validate from the current candidate packages**

Run the three build/validation commands from Task 9 again.

Expected: deterministic hashes for the two core datasets, 10 unified events, expected task coverage, and validation exit 0.

- [ ] **Step 4: Inspect final generated records**

Read the first and last records of both JSONL files and confirm UTF-8 Chinese text, stable IDs, standard `messages`, event-level `split`, metadata lineage, and absence of `hidden`/`evaluator_only` source paths.

- [ ] **Step 5: Report the exact verified status**

Report test count, generated record counts, split counts, validation status, dry-run status, and any inability to perform a real GPU fine-tune due to missing model downloads or optional training dependencies. Do not claim an actual model was trained unless the full training command completed and produced adapter artifacts.
