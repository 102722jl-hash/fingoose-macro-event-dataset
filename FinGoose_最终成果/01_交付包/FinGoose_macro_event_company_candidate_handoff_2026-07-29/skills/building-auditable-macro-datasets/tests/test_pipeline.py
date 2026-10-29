import json

from audit_outputs import (
    assemble_candidate_master,
    build_event_splits,
    canonical_sha256,
    candidate_eligibility,
    compare_artifact_sets,
    partition_candidates,
    validate_replay_inputs,
)
from macro_dataset_pipeline import (
    materialize_command,
    normalize_validation_report_paths,
    prepare_candidate_run,
    validation_outcome,
    write_run_configs,
)


def test_failed_event_is_quarantined_without_blocking_closed_event():
    eligible, quarantine = partition_candidates([
        {"event_id": "event-ok", "closure_status": "CLOSED", "errors": [], "warnings": []},
        {"event_id": "event-bad", "closure_status": "OPEN", "errors": ["SOURCE_EVIDENCE_INCOMPLETE"], "warnings": []},
    ])
    assert [row["event_id"] for row in eligible] == ["event-ok"]
    assert quarantine == [{
        "event_id": "event-bad",
        "quarantine_reasons": ["OPEN", "SOURCE_EVIDENCE_INCOMPLETE"],
    }]


def test_candidate_sft_requires_zero_errors_and_warnings():
    assert candidate_eligibility({"closure_status": "CLOSED", "errors": [], "warnings": []}) is True
    assert candidate_eligibility({"closure_status": "CLOSED", "errors": [], "warnings": ["x"]}) is False


def test_accepted_content_replaces_existing_event_and_adds_new_event():
    base = [
        {"event_id": "event-01", "title_zh": "旧标题"},
        {"event_id": "event-02", "title_zh": "保留事件"},
    ]
    updated = {"event_id": "event-01", "title_zh": "更新标题"}
    added = {"event_id": "event-11", "title_zh": "新增事件"}
    accepted = [
        {
            "event_id": "event-01",
            "operation": "UPSERT",
            "unified_event": updated,
            "evidence_ids": ["evidence-01"],
            "content_sha256": canonical_sha256(updated),
        },
        {
            "event_id": "event-11",
            "operation": "UPSERT",
            "unified_event": added,
            "evidence_ids": ["evidence-11"],
            "content_sha256": canonical_sha256(added),
        },
    ]
    result = assemble_candidate_master(base, accepted)
    assert [row["event_id"] for row in result] == ["event-01", "event-02", "event-11"]
    assert result[0]["title_zh"] == "更新标题"


def test_split_preserves_existing_allows_override_and_hashes_new_events():
    base_splits = {
        "train": ["event-01"],
        "validation": ["event-09"],
        "test": ["event-10"],
    }
    policy = {
        "method": "sha256_mod_100",
        "version": "split-v1",
        "train_max": 79,
        "validation_max": 89,
    }
    accepted = [
        {"event_id": "event-01", "split_assignment": "test"},
        {"event_id": "event-11", "split_assignment": "validation"},
        {"event_id": "event-12"},
    ]
    left = build_event_splits(
        ["event-01", "event-09", "event-10", "event-11", "event-12"],
        base_splits,
        accepted,
        policy,
    )
    right = build_event_splits(
        ["event-01", "event-09", "event-10", "event-11", "event-12"],
        base_splits,
        accepted,
        policy,
    )
    assert "event-01" in left["train"]
    assert "event-11" in left["validation"]
    assert left == right
    assert sum("event-12" in ids for ids in left.values()) == 1


def test_run_configs_point_only_to_run_local_candidate_outputs(tmp_path):
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    dataset_path, training_path = write_run_configs(
        run_dir,
        {"dataset_version": "v1", "sources": {}, "outputs": {}, "splits": {}},
        {"config_version": "train-v1"},
        {"train": ["event-01"], "validation": [], "test": []},
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    training = json.loads(training_path.read_text(encoding="utf-8"))
    assert dataset["outputs"]["unified_events"] == "candidate_master_data.jsonl"
    assert dataset["outputs"]["sft_dataset"] == "candidate_sft_dataset.jsonl"
    assert dataset["project_root"] == str(run_dir.resolve())
    assert sorted(dataset["sources"]["frozen"]["files"]) == [
        "accepted_content",
        "accepted_evidence",
        "base_dataset_config",
        "base_training_config",
        "base_unified_events",
        "profile",
    ]
    assert training["dataset_config"] == "dataset.run.json"
    assert training["sft_dataset"] == "candidate_sft_dataset.jsonl"


def test_command_materialization_replaces_only_explicit_placeholders(tmp_path):
    run_config = tmp_path / "dataset.run.json"
    training_config = tmp_path / "sft.run.json"
    command = [
        "python",
        "script.py",
        "{run_config}",
        "prefix-{run_config}",
        "{run_training_config}",
    ]
    assert materialize_command(command, run_config, training_config) == [
        "python",
        "script.py",
        str(run_config),
        "prefix-{run_config}",
        str(training_config),
    ]


def test_validation_requires_success_and_zero_errors_and_warnings():
    clean = {"valid": True, "errors": [], "warnings": []}
    assert validation_outcome([0, 0], clean)["status"] == "CANDIDATE_SFT_ELIGIBLE"
    assert validation_outcome([0, 1], clean)["status"] == "VALIDATION_FAILED"
    assert validation_outcome([0, 0], {**clean, "warnings": ["x"]})["status"] == "VALIDATION_FAILED"


def test_build_assembles_only_frozen_baseline_and_accepted_content(tmp_path):
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    base = {"event_id": "event-01", "title_zh": "旧标题"}
    updated = {"event_id": "event-01", "title_zh": "新标题"}
    added = {"event_id": "event-11", "title_zh": "新增事件"}
    (run_dir / "base_unified_events.jsonl").write_text(
        json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    accepted = [
        {
            "event_id": "event-01",
            "operation": "UPSERT",
            "unified_event": updated,
            "evidence_ids": ["e1"],
            "content_sha256": canonical_sha256(updated),
        },
        {
            "event_id": "event-11",
            "operation": "UPSERT",
            "unified_event": added,
            "evidence_ids": ["e11"],
            "content_sha256": canonical_sha256(added),
        },
    ]
    (run_dir / "accepted_content.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in accepted),
        encoding="utf-8",
    )
    (run_dir / "base_dataset_config.json").write_text(
        json.dumps({"dataset_version": "v1", "splits": {"train": ["event-01"], "validation": [], "test": []}}),
        encoding="utf-8",
    )
    (run_dir / "base_training_config.json").write_text(
        json.dumps({"config_version": "train-v1"}), encoding="utf-8"
    )
    profile = {
        "split_policy": {
            "method": "sha256_mod_100",
            "version": "split-v1",
            "train_max": 79,
            "validation_max": 89,
        }
    }
    result = prepare_candidate_run(run_dir, profile)
    rows = [json.loads(line) for line in result["candidate_master_data"].read_text(encoding="utf-8").splitlines()]
    assert [row["event_id"] for row in rows] == ["event-01", "event-11"]
    assert rows[0]["title_zh"] == "新标题"
    assert result["run_config"].parent == run_dir
    assert result["run_training_config"].parent == run_dir


def test_replay_artifact_sets_must_have_identical_hashes(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root in (left, right):
        (root / "candidate_master_data.jsonl").write_text('{"event_id":"event-1"}\n', encoding="utf-8")
        (root / "candidate_sft_dataset.jsonl").write_text('{"sample_id":"sample-1"}\n', encoding="utf-8")
        (root / "validation_report.json").write_text('{"valid":true}\n', encoding="utf-8")
    report = compare_artifact_sets(left, right, (
        "candidate_master_data.jsonl", "candidate_sft_dataset.jsonl", "validation_report.json"
    ))
    assert report["stable"] is True
    assert all(row["matches"] for row in report["artifacts"])


def test_replay_detects_changed_artifact(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "x.json").write_text('{"x":1}\n', encoding="utf-8")
    (right / "x.json").write_text('{"x":2}\n', encoding="utf-8")
    assert compare_artifact_sets(left, right, ("x.json",))["stable"] is False


def test_replay_requires_frozen_evidence_content_baseline_and_configs(tmp_path):
    (tmp_path / "snapshots").mkdir()
    for name in (
        "profile.json",
        "base_dataset_config.json",
        "base_training_config.json",
        "base_unified_events.jsonl",
        "accepted_evidence.jsonl",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    assert validate_replay_inputs(tmp_path) == ["ACCEPTED_CONTENT_MISSING"]
    (tmp_path / "accepted_content.jsonl").write_text("{}\n", encoding="utf-8")
    assert validate_replay_inputs(tmp_path) == []


def test_validation_report_paths_are_run_local_before_sha_comparison():
    report = {
        "validated_artifacts": {
            "unified_events": {"path": "C:/left/replay-1/candidate_master_data.jsonl", "sha256": "a"},
            "sft_dataset": {"path": "C:/left/replay-1/candidate_sft_dataset.jsonl", "sha256": "b"},
        }
    }
    normalized = normalize_validation_report_paths(report)
    assert normalized["validated_artifacts"]["unified_events"]["path"] == "candidate_master_data.jsonl"
    assert normalized["validated_artifacts"]["sft_dataset"]["path"] == "candidate_sft_dataset.jsonl"
