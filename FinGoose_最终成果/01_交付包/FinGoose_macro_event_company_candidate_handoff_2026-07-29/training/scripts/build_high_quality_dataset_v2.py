"""Build content-aligned artifacts with horizon-specific answers."""

from __future__ import annotations

import argparse
from pathlib import Path

from fingoose_training.artifacts import build_manifest, resolve_output_paths, resolve_project_root, resolve_source_paths, write_json, write_jsonl
from fingoose_training.loaders import load_source_bundle, read_json
from fingoose_training.splits import build_event_split_index, tag_samples
from fingoose_training.sft_projector_impl_005 import project_sft_samples
from fingoose_training.ui_reference import load_ui_reference
from fingoose_training.unified_builder_impl_003 import build_unified_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build high-quality FinGoose artifacts.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    config_path = args.config.resolve()
    config = read_json(config_path)
    project_root = resolve_project_root(config_path, config)
    source, _ = load_source_bundle(project_root, config)
    ui_path = (project_root / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js").resolve()
    unified = build_unified_events(source, config["dataset_version"], ui_reference=load_ui_reference(ui_path))
    outputs = resolve_output_paths(config_path, config)
    write_jsonl(outputs["unified_events"], unified)
    samples = tag_samples(project_sft_samples(unified, config.get("task_types")), config["splits"])
    write_jsonl(outputs["sft_dataset"], samples)
    split_index = build_event_split_index(config["splits"])
    write_json(outputs["split_manifest"], {"dataset_version": config["dataset_version"], "splits": config["splits"], "event_to_split": dict(sorted(split_index.items()))})
    source_paths = resolve_source_paths(project_root, config)
    source_paths["ui_reference_bundle"] = ui_path
    write_json(outputs["manifest"], build_manifest(dataset_version=config["dataset_version"], source_paths=source_paths, output_paths=outputs, unified_events=unified, sft_samples=samples))
    print(f"wrote {len(unified)} unified events to {outputs['unified_events']}")
    print(f"wrote {len(samples)} SFT samples to {outputs['sft_dataset']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
