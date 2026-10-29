"""Strict readers for FinGoose JSON and JSONL source packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ui_reference import load_ui_reference


FORBIDDEN_SOURCE_PARTS = {"hidden", "evaluator_only"}


class JsonlError(ValueError):
    """Raised when a JSONL source cannot be read without ambiguity."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def read_jsonl(path: Path, unique_key: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Any] = set()
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
            if unique_key:
                if unique_key not in row or row[unique_key] in (None, ""):
                    raise JsonlError(f"{path}:{line_number}: missing {unique_key}")
                value = row[unique_key]
                if value in seen:
                    raise JsonlError(
                        f"{path}:{line_number}: duplicate {unique_key}={value}"
                    )
                seen.add(value)
            rows.append(row)
    return rows


def load_source_bundle(
    project_root: Path, config: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Path]]:
    bundle: dict[str, list[dict[str, Any]]] = {}
    source_paths: dict[str, Path] = {}
    for source_name, source_config in config.get("sources", {}).items():
        base_dir = (project_root / source_config["base_dir"]).resolve()
        for logical_name, filename in source_config.get("files", {}).items():
            path = (base_dir / filename).resolve()
            lowered_parts = {part.lower() for part in path.parts}
            if lowered_parts & FORBIDDEN_SOURCE_PARTS:
                raise ValueError(
                    f"{source_name}.{logical_name}: forbidden source path {path}"
                )
            if not path.is_file():
                raise FileNotFoundError(f"{source_name}.{logical_name}: missing {path}")
            bundle[logical_name] = read_jsonl(path)
            source_paths[logical_name] = path
    return bundle, source_paths

def resolve_ui_reference_path(project_root: Path, config: dict[str, Any]) -> Path:
    relative = (config.get("content_alignment") or {}).get("ui_reference_path")
    if not relative:
        raise ValueError("content alignment requires ui_reference_path")
    path = (project_root / relative).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"ui reference missing: {path}")
    return path

def load_ui_reference_bundle(project_root: Path, config: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    path = resolve_ui_reference_path(project_root, config)
    return load_ui_reference(path), path
