"""Date-precision adapter for the strict Q&A source snapshot function."""

from __future__ import annotations

import calendar
from pathlib import Path
from typing import Any, Callable, Mapping

from fingoose_qa_sources_v2 import snapshot_source as _strict_snapshot_source


def _normalize_publication_time(value: str) -> tuple[str, str | None]:
    if len(value) == 10:
        return value + "T23:59:59.999999Z", "DATE"
    if len(value) == 7:
        year, month = (int(part) for part in value.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return f"{value}-{last_day:02d}T23:59:59.999999Z", "MONTH"
    return value, None


def snapshot_source(
    target: Mapping[str, Any],
    *,
    cutoff_at: str,
    output_root: Path,
    fetch_bytes: Callable[[str], bytes],
    accessed_at: str,
) -> dict[str, Any]:
    original = target.get("first_public_at")
    normalized = dict(target)
    precision: str | None = None
    if original:
        normalized_value, precision = _normalize_publication_time(str(original))
        normalized["first_public_at"] = normalized_value
    result = _strict_snapshot_source(
        normalized,
        cutoff_at=cutoff_at,
        output_root=output_root,
        fetch_bytes=fetch_bytes,
        accessed_at=accessed_at,
    )
    result["first_public_at"] = original
    if precision:
        result["first_public_at_precision"] = precision
        result["publication_time_basis"] = "DATE_VALUE_END_OF_DAY_UPPER_BOUND"
    return result


__all__ = ["snapshot_source"]
