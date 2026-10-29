import json
from pathlib import Path

from fingoose_training.artifacts import sha256_file
from scripts.build_sft_dataset import main as build_sft_main
from scripts.build_unified_dataset import main as build_unified_main
from scripts.validate_dataset import main as validate_main
from test_unified_builder import complete_source


SOURCE_GROUPS = {
    "macro": [
        "event_episodes",
        "event_milestones",
        "transmission_graphs",
        "macro_market_windows",
        "macro_sources",
    ],
    "industry": [
        "event_industry_mappings",
        "industry_mechanism_chains",
        "industry_market_windows",
        "industry_evidence",
    ],
    "company": [
        "event_company_map",
        "company_mechanism_chains",
        "direction_assessments",
        "company_evidence",
        "company_market_windows",
        "company_confounders",
        "company_counterevidence_reviews",
        "trading_status_reviews",
    ],
    "qa": ["qa_cases", "qa_answers", "qa_sources"],
}


def _write_jsonl(path: Path, rows: list[dict]):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _make_config(root: Path) -> Path:
    source = complete_source()
    sources = {}
    for group, logical_names in SOURCE_GROUPS.items():
        base_dir = root / group
        base_dir.mkdir(exist_ok=True)
        files = {}
        for logical_name in logical_names:
            filename = f"{logical_name}.jsonl"
            _write_jsonl(base_dir / filename, source[logical_name])
            files[logical_name] = filename
        sources[group] = {"base_dir": group, "files": files}

    config_dir = root / "configs"
    output_dir = root / "out"
    config_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    config = {
        "dataset_version": "test-unified-v1",
        "project_root": "..",
        "sources": sources,
        "outputs": {
            "unified_events": "../out/unified_events.jsonl",
            "sft_dataset": "../out/sft_dataset.jsonl",
            "split_manifest": "../out/split_manifest.json",
            "manifest": "../out/manifest.json",
            "validation_report": "../out/validation_report.json",
        },
        "splits": {"train": ["event-01"], "validation": [], "test": []},
        "task_types": [
            "EVENT_ANALYSIS",
            "INDUSTRY_IMPACT",
            "COMPANY_IMPACT",
            "EVENT_QA",
        ],
    }
    config_path = config_dir / "dataset.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return config_path


def test_build_and_validate_clis_are_deterministic(scratch_path):
    root = scratch_path / "cli_project"
    root.mkdir(exist_ok=True)
    config_path = _make_config(root)

    assert build_unified_main(["--config", str(config_path)]) == 0
    first_unified = (root / "out" / "unified_events.jsonl").read_bytes()
    assert build_sft_main(["--config", str(config_path)]) == 0
    first_sft = (root / "out" / "sft_dataset.jsonl").read_bytes()
    assert validate_main(["--config", str(config_path)]) == 0

    assert build_unified_main(["--config", str(config_path)]) == 0
    assert build_sft_main(["--config", str(config_path)]) == 0
    assert (root / "out" / "unified_events.jsonl").read_bytes() == first_unified
    assert (root / "out" / "sft_dataset.jsonl").read_bytes() == first_sft

    report = json.loads((root / "out" / "validation_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["dataset_version"] == "test-unified-v1"
    assert report["counts"] == {"unified_events": 1, "sft_samples": 4}
    for artifact_name, filename in {
        "unified_events": "unified_events.jsonl",
        "sft_dataset": "sft_dataset.jsonl",
        "split_manifest": "split_manifest.json",
    }.items():
        assert report["validated_artifacts"][artifact_name]["sha256"] == sha256_file(
            root / "out" / filename
        )
    assert manifest["record_counts"]["sft_samples"] == 4
    assert (root / "out" / "split_manifest.json").is_file()
