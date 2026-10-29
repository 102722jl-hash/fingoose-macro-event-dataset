"""Treat partially populated candidate evidence as an explicit gap."""

from __future__ import annotations

from typing import Any, Mapping

from .validation_impl_002 import *
from .validation_impl_002 import _reasoning_codes, validate_datasets as _validate_v2


def validate_reasoning_chain(metadata: Mapping[str, Any], task_type: str | None = None) -> list[str]:
    return [code for code in _reasoning_codes(metadata, task_type) if code != "REASONING_MISSING_EVIDENCE_FABRICATED"]


def validate_datasets(
    unified_events: list[dict[str, Any]],
    sft_samples: list[dict[str, Any]],
    expected_events: set[str],
    expected_task_types: set[str] | None = None,
) -> dict[str, Any]:
    report = _validate_v2(unified_events, sft_samples, expected_events, expected_task_types)
    report["errors"] = [error for error in report["errors"] if error["code"] != "REASONING_MISSING_EVIDENCE_FABRICATED"]
    report["valid"] = not report["errors"]
    return report


__all__ = [
    "ALLOWED_SPLITS", "ALLOWED_TASK_TYPES", "EXPECTED_ROLES", "FORBIDDEN_TOKENS",
    "MAX_MESSAGE_CHARS", "METADATA_LIST_FIELDS", "TRUNCATION_MARKER",
    "validate_datasets", "validate_reasoning_chain",
]
