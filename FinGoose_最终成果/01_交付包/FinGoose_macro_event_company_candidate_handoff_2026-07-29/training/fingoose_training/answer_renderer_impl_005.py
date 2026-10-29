"""Clean QA rendering over the final event/industry/company renderer."""

from __future__ import annotations

from typing import Any, Mapping

from . import answer_renderer as _core
from .answer_renderer_impl_003 import render_answer as _render_other
from .research_content import select_task_content


def _horizon_text(value: Any, fallback: str) -> str:
    if isinstance(value, Mapping):
        return str(value.get("reasoning_zh") or value.get("summary_zh") or fallback).strip()
    return str(value or fallback).strip()


def render_answer(task_type: str, *, event: Mapping[str, Any], sample: Mapping[str, Any], chain: Mapping[str, Any] | None = None) -> str:
    if task_type != "EVENT_QA":
        return _render_other(task_type, event=event, sample=sample, chain=chain)
    content = select_task_content(event, sample)
    direct = _core._short(content.get("direct_answer_zh") or "材料不足，无法形成确定性回答。", 300)
    facts = content.get("official_facts") or []
    inferences = content.get("research_inferences") or []
    calculated = content.get("calculated_facts") or []
    fact_lines = [f"{_core._short(row.get('fact_zh') or row.get('original_quote'), 130)}（证据 ID：{row.get('evidence_id') or '无'}）" for row in facts[:2] if isinstance(row, Mapping)] or ["未找到可直接核验的官方事实，保留证据缺口"]
    inference_lines = [f"{_core._short(row.get('inference_zh') or row.get('statement_zh'), 150)}（证据 ID：{_core._ids(row.get('evidence_ids'))}）" for row in inferences[:2] if isinstance(row, Mapping)] or ["机制与方向属于研究推断，不能升级为来源事实"]
    horizon = content.get("horizon_reasoning_zh") or {}
    sections = [
        ("直接回答", [direct]),
        ("来源事实", fact_lines),
        ("研究推断", inference_lines),
        ("即时影响", [_horizon_text(horizon.get("IMMEDIATE"), "按当前问题材料保持不确定")]),
        ("短期影响", [_horizon_text(horizon.get("SHORT_TERM"), "按当前问题材料保持不确定")]),
        ("中期影响", [_horizon_text(horizon.get("MEDIUM_TERM"), "按当前问题材料保持不确定")]),
        ("行情验证", ["已提供计算窗口，行情只用于验证，不单独证明因果。" if calculated else "未提供可用计算事实，不能用行情填补证据缺口"]),
        ("证据边界", [_core._review_boundary(content)]),
    ]
    return _core.render_sections(sections, 1250)


__all__ = ["render_answer"]
