"""Final high-quality validation entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from fingoose_training.artifacts import resolve_output_paths, sha256_file, write_json
from fingoose_training.loaders import read_json, read_jsonl
from fingoose_training.validation_impl_005 import validate_datasets


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate content-aligned artifacts.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    config_path = args.config.resolve()
    config = read_json(config_path)
    outputs = resolve_output_paths(config_path, config)
    unified = read_jsonl(outputs["unified_events"], unique_key="event_id")
    samples = read_jsonl(outputs["sft_dataset"], unique_key="sample_id")
    expected = {event_id for values in config["splits"].values() for event_id in values}
    report = validate_datasets(unified, samples, expected, set(config["task_types"]))
    report["dataset_version"] = config["dataset_version"]
    report["validated_artifacts"] = {name: {"path": str(outputs[name]), "sha256": sha256_file(outputs[name])} for name in ("unified_events", "sft_dataset", "split_manifest")}
    write_json(outputs["validation_report"], report)
    print(f"validation {'passed' if report['valid'] else 'failed'}: {len(report['errors'])} errors, {len(report.get('warnings', []))} warnings")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
