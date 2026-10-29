"""Refined renderer with horizon-specific summaries."""

from __future__ import annotations

from typing import Any, Mapping

from . import answer_renderer as _base
from .research_content import select_task_content


def _horizon_line(content: Mapping[str, Any], horizon: str) -> str:
    block = (content.get("horizon_analysis") or {}).get(horizon) or {}
    rows = block.get("impact_rows") or []
    pieces = []
    for row in rows[:3]:
        pieces.append(f"{row.get('scope_name_zh') or row.get('scope_id')}：{row.get('direction', 'UNKNOWN')}，{str(row.get('condition_zh') or row.get('detail_zh') or '').strip()}")
    return f"{horizon}阶段" + "；".join(pieces) + f"。证据 ID：{_base._ids(block.get('evidence_ids'), 4)}。"


def _event_answer(event: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    title = content.get("title_zh") or event.get("title_zh") or event.get("event_id")
    sections = [
        ("结论", [f"{title}是公开冲击，主要通过风险偏好、全球需求和避险需求传导；行业方向存在分化，当前为候选研究结论。"]),
        ("来源事实", _base._source_lines(content)),
        ("即时影响", [_horizon_line(content, "IMMEDIATE")]),
        ("短期影响", [_horizon_line(content, "SHORT_TERM")]),
        ("中期影响", [_horizon_line(content, "MEDIUM_TERM")]),
        ("行情验证", _base._market_lines(content)),
        ("证据边界", [_base._review_boundary(content) + " " + str((content.get("boundaries") or {}).get("limitations_zh") or "行情仅作验证")]),
    ]
    return _base.render_sections(sections, 1250)


def render_answer(task_type: str, *, event: Mapping[str, Any], sample: Mapping[str, Any], chain: Mapping[str, Any] | None = None) -> str:
    content = select_task_content(event, sample)
    if task_type == "EVENT_ANALYSIS":
        return _event_answer(event, content)
    return _base.render_answer(task_type, event=event, sample=sample, chain=chain)


__all__ = ["render_answer"]
