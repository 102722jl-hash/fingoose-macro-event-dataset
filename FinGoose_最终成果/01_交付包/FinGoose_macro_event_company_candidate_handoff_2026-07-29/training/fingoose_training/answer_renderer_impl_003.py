"""Final event renderer with explicit primary WHO evidence linkage."""

from __future__ import annotations

from typing import Any, Mapping

from . import answer_renderer_impl_001 as _base
from .research_content import select_task_content


def render_answer(task_type: str, *, event: Mapping[str, Any], sample: Mapping[str, Any], chain: Mapping[str, Any] | None = None) -> str:
    if task_type != "EVENT_ANALYSIS":
        return _base.render_answer(task_type, event=event, sample=sample, chain=chain)
    content = select_task_content(event, sample)
    source = _base._base._source_lines(content)
    all_ids = content.get("answer_evidence_ids") or []
    preferred = next((eid for eid in all_ids if str(eid).endswith("who-pandemic")), None)
    preferred = preferred or next(iter(content.get("primary_answer_evidence_ids") or []), None)
    if preferred and all(str(preferred) not in line for line in source):
        source.append(f"核心事件事实保留证据 ID：{preferred}；证据状态按原始原文与定位完整性判断。")
    title = content.get("title_zh") or event.get("event_id")
    sections = [
        ("结论", [f"{title}是公开冲击，主要通过风险偏好、全球需求和避险需求传导；行业方向存在分化，当前为候选研究结论。"]),
        ("来源事实", source),
        ("即时影响", [_base._horizon_line(content, "IMMEDIATE")]),
        ("短期影响", [_base._horizon_line(content, "SHORT_TERM")]),
        ("中期影响", [_base._horizon_line(content, "MEDIUM_TERM")]),
        ("行情验证", _base._base._market_lines(content)),
        ("证据边界", [_base._base._review_boundary(content) + " " + str((content.get("boundaries") or {}).get("limitations_zh") or "行情仅作验证")]),
    ]
    return _base._base.render_sections(sections, 1250)


__all__ = ["render_answer"]
