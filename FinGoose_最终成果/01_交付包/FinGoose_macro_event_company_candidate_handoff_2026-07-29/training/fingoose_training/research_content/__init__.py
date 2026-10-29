"""Stable public path for the content contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_source = Path(__file__).resolve().parent.parent / "research_content.py"
_spec = importlib.util.spec_from_file_location("_fingoose_research_content_base", _source)
_base = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_base)

CONTENT_SCHEMA_VERSION = _base.CONTENT_SCHEMA_VERSION
ContentAlignmentError = _base.ContentAlignmentError
HORIZONS = _base.HORIZONS
select_task_content = _base.select_task_content


def _base_build_event_research_content(ui_event):
    content = _base.build_event_research_content(ui_event)
    for horizon, label in (("IMMEDIATE", "即时"), ("SHORT_TERM", "短期"), ("MEDIUM_TERM", "中期")):
        block = content.get("horizon_analysis", {}).get(horizon) or {}
        rows = block.get("impact_rows") or []
        block["summary_zh"] = "；".join(
            f"{row.get('scope_name_zh')}在{label}阶段为{row.get('direction', 'UNKNOWN')}，{row.get('condition_zh') or row.get('detail_zh') or '保持候选边界'}"
            for row in rows[:3]
        )
        content["horizon_analysis"][horizon] = block
    return content


# Define the compatibility base before importing the version chain: impl_001
# imports this package while impl_004 is being initialized.
build_event_research_content = _base_build_event_research_content

from ..research_content_impl_004 import (  # noqa: E402
    build_event_research_content as _build_v4,
)

build_event_research_content = _build_v4


__all__ = ["CONTENT_SCHEMA_VERSION", "ContentAlignmentError", "HORIZONS", "build_event_research_content", "select_task_content"]
