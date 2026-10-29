import re
from datetime import datetime
from typing import Any


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIMESTAMP_PRECISIONS = {"MINUTE", "SECOND", "MILLISECOND"}


def _required(errors: list[str], value: Any, field: str) -> None:
    if value is None or value == "" or value == []:
        errors.append(f"{field} is required")


def _validate_time(record: dict[str, Any], stem: str, errors: list[str]) -> None:
    value = record.get(stem)
    precision = record.get(f"{stem}_precision")
    evidence = record.get(f"{stem}_evidence")

    _required(errors, value, stem)
    _required(errors, precision, f"{stem}_precision")
    if value is None or precision is None:
        return

    if precision == "DATE":
        if not isinstance(value, str) or not DATE_RE.fullmatch(value):
            errors.append(f"unsupported {stem} precision")
    elif precision in TIMESTAMP_PRECISIONS:
        if not isinstance(value, str):
            errors.append(f"invalid {stem} timestamp")
        else:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"invalid {stem} timestamp")
            else:
                if parsed.tzinfo is None:
                    errors.append(f"{stem} timezone is required")
    else:
        errors.append(f"unsupported {stem} precision")

    if not isinstance(evidence, dict):
        errors.append(f"{stem}_evidence is required")
        return
    for field in ("source_id", "locator", "quote"):
        _required(errors, evidence.get(field), f"{stem}_evidence.{field}")


def _validate_replacement(record: dict[str, Any], errors: list[str]) -> None:
    if not record.get("semantic_change"):
        return
    audit = record.get("replacement_audit")
    if not isinstance(audit, dict):
        errors.append("missing replacement audit")
        return

    required = (
        "original_fact",
        "original_source_ids",
        "replacement_fact",
        "replacement_source_ids",
        "replacement_reason",
        "review_result",
    )
    for field in required:
        _required(errors, audit.get(field), f"replacement audit {field}")
    if not audit.get("affected_records"):
        errors.append("replacement audit affected_records must be non-empty")


def validate_verified_node(record: dict[str, Any]) -> list[str]:
    if record.get("evidence_status") != "VERIFIED_EXISTING":
        return []

    errors: list[str] = []
    for field in ("fast_node_id", "event_id", "fact"):
        _required(errors, record.get(field), field)

    if not record.get("source_ids"):
        errors.append("source_ids must be non-empty")

    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be non-empty")
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"evidence[{index}] must be an object")
                continue
            for field in ("source_id", "source_tier", "url", "quote", "locator"):
                _required(errors, item.get(field), f"evidence[{index}].{field}")

    _validate_time(record, "occurred_at", errors)
    _validate_time(record, "first_public_at", errors)
    _validate_replacement(record, errors)
    return errors
