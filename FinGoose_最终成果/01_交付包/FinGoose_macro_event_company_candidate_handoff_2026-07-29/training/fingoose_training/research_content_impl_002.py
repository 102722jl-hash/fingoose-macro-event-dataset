"""Ensure horizon summaries carry distinct stage-specific directions."""

from __future__ import annotations

from typing import Any, Mapping

from .research_content_impl_001 import build_event_research_content as _build
from .research_content import select_task_content


def build_event_research_content(ui_event: Mapping[str, Any]) -> dict[str, Any]:
    content = _build(ui_event)
    for horizon, label in (("IMMEDIATE", "即时"), ("SHORT_TERM", "短期"), ("MEDIUM_TERM", "中期")):
        block = content.get("horizon_analysis", {}).get(horizon) or {}
        rows = block.get("impact_rows") or []
        block["summary_zh"] = "；".join(
            f"{row.get('scope_name_zh')}在{label}阶段为{row.get('direction', 'UNKNOWN')}，{row.get('condition_zh') or row.get('detail_zh') or '保持候选边界'}"
            for row in rows[:3]
        )
        content["horizon_analysis"][horizon] = block
    return content


__all__ = ["build_event_research_content", "select_task_content"]
