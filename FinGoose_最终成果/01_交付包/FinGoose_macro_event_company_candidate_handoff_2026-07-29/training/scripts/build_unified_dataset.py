from __future__ import annotations

import argparse
from pathlib import Path

from fingoose_training.artifacts import resolve_output_paths, resolve_project_root, write_jsonl
from fingoose_training.loaders import load_source_bundle, load_ui_reference_bundle, read_json
from fingoose_training.unified_builder import build_unified_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build event-centered FinGoose records.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    config = read_json(config_path)
    project_root = resolve_project_root(config_path, config)
    source, _ = load_source_bundle(project_root, config)
    if config.get("content_alignment"):
        ui_reference, _ = load_ui_reference_bundle(project_root, config)
        records = build_unified_events(source, config["dataset_version"], ui_reference=ui_reference)
    else:
        records = build_unified_events(source, config["dataset_version"])
    output_path = resolve_output_paths(config_path, config)["unified_events"]
    write_jsonl(output_path, records)
    print(f"wrote {len(records)} unified events to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
