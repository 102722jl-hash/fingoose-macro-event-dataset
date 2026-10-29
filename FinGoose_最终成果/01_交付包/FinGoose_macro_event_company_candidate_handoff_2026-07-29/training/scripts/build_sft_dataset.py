from __future__ import annotations

import argparse
from pathlib import Path

from fingoose_training.artifacts import (
    build_manifest,
    resolve_output_paths,
    resolve_project_root,
    resolve_source_paths,
    write_json,
    write_jsonl,
)
from fingoose_training.loaders import read_json, read_jsonl
from fingoose_training.sft_projector import project_sft_samples
from fingoose_training.splits import build_event_split_index, tag_samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project unified events to SFT messages.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    config = read_json(config_path)
    output_paths = resolve_output_paths(config_path, config)
    unified_events = read_jsonl(output_paths["unified_events"], unique_key="event_id")
    projected = project_sft_samples(unified_events, config.get("task_types"))
    samples = tag_samples(projected, config["splits"])
    write_jsonl(output_paths["sft_dataset"], samples)

    split_index = build_event_split_index(config["splits"])
    write_json(
        output_paths["split_manifest"],
        {
            "dataset_version": config["dataset_version"],
            "splits": config["splits"],
            "event_to_split": dict(sorted(split_index.items())),
        },
    )
    project_root = resolve_project_root(config_path, config)
    manifest = build_manifest(
        dataset_version=config["dataset_version"],
        source_paths=resolve_source_paths(project_root, config),
        output_paths=output_paths,
        unified_events=unified_events,
        sft_samples=samples,
    )
    write_json(output_paths["manifest"], manifest)
    print(f"wrote {len(samples)} SFT samples to {output_paths['sft_dataset']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
