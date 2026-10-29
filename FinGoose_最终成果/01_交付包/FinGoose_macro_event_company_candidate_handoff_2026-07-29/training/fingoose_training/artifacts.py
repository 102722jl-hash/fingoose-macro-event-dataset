"""Deterministic artifact writing and hashing helpers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def resolve_project_root(config_path: Path, config: dict[str, Any]) -> Path:
    return (config_path.parent / config.get("project_root", "../..")).resolve()


def resolve_output_paths(
    config_path: Path, config: dict[str, Any]
) -> dict[str, Path]:
    return {
        name: (config_path.parent / relative_path).resolve()
        for name, relative_path in config["outputs"].items()
    }


def resolve_source_paths(
    project_root: Path, config: dict[str, Any]
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for source_config in config["sources"].values():
        base_dir = (project_root / source_config["base_dir"]).resolve()
        for logical_name, filename in source_config["files"].items():
            paths[logical_name] = (base_dir / filename).resolve()
    alignment = config.get("content_alignment") or {}
    if alignment.get("ui_reference_path"):
        paths["ui_reference_bundle"] = (project_root / alignment["ui_reference_path"]).resolve()
    return paths


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    temporary.replace(path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    dataset_version: str,
    source_paths: dict[str, Path],
    output_paths: dict[str, Path],
    unified_events: list[dict[str, Any]],
    sft_samples: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dataset_version": dataset_version,
        "source_files": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in sorted(source_paths.items())
        },
        "artifacts": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in sorted(output_paths.items())
            if name in {"unified_events", "sft_dataset", "split_manifest"}
            and path.is_file()
        },
        "record_counts": {
            "unified_events": len(unified_events),
            "sft_samples": len(sft_samples),
        },
        "task_counts": dict(
            sorted(Counter(row["task_type"] for row in sft_samples).items())
        ),
        "event_counts": dict(
            sorted(Counter(row["event_id"] for row in sft_samples).items())
        ),
        "split_counts": dict(
            sorted(Counter(row["split"] for row in sft_samples).items())
        ),
    }
