from __future__ import annotations

import argparse
from pathlib import Path

from fingoose_training.artifacts import (
    resolve_output_paths,
    sha256_file,
    write_json,
)
from fingoose_training.loaders import read_json, read_jsonl
from fingoose_training.validation import validate_datasets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate FinGoose training datasets.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    config = read_json(config_path)
    output_paths = resolve_output_paths(config_path, config)
    unified_events = read_jsonl(output_paths["unified_events"], unique_key="event_id")
    sft_samples = read_jsonl(output_paths["sft_dataset"], unique_key="sample_id")
    expected_events = {
        event_id for event_ids in config["splits"].values() for event_id in event_ids
    }
    report = validate_datasets(
        unified_events,
        sft_samples,
        expected_events,
        expected_task_types=set(config["task_types"]),
    )
    report["dataset_version"] = config["dataset_version"]
    report["validated_artifacts"] = {
        artifact_name: {
            "path": str(output_paths[artifact_name]),
            "sha256": sha256_file(output_paths[artifact_name]),
        }
        for artifact_name in ("unified_events", "sft_dataset", "split_manifest")
    }
    write_json(output_paths["validation_report"], report)
    print(
        f"validation {'passed' if report['valid'] else 'failed'}: "
        f"{len(report['errors'])} errors, {len(report['warnings'])} warnings"
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
