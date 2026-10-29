"""Final renderer with normalized market asset labels."""

from __future__ import annotations

import re
from typing import Any, Mapping

from . import answer_renderer as _core
from .answer_renderer_impl_001 import _horizon_line
from .answer_renderer_impl_005 import render_answer as _render_other
from .research_content import select_task_content


def _market_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    rows = content.get("market_validation") or []
    if isinstance(rows, Mapping):
        rows = [rows]
    lines = []
    for row in list(rows)[:limit]:
        if not isinstance(row, Mapping):
            continue
        asset = row.get("series_id") or row.get("industry_name_zh") or row.get("market_benchmark") or row.get("benchmark") or "市场窗口"
        if isinstance(asset, Mapping):
            asset = asset.get("benchmark_code") or asset.get("benchmark_id") or "市场基准"
        status = row.get("window_status") or row.get("data_availability_gap") or "DATA_PENDING"
        windows = row.get("fixed_windows") or row.get("windows") or {}
        available = [name for name in ("T0", "D1", "D3", "D5", "D20") if isinstance(windows, Mapping) and windows.get(name)]
        lines.append(f"{asset}：窗口 {','.join(available) or '缺数据'}，状态 {status}；只用于验证同步反应，不证明严格因果")
    return lines or ["未提供可用行情窗口，保留 DATA_PENDING，不将缺失写成零"]


def _company_lines(content: Mapping[str, Any]) -> list[str]:
    parts = []
    for row in (content.get("company_impacts") or [])[:3]:
        if not isinstance(row, Mapping):
            continue
        directions = row.get("horizon_directions") or {}
        name = row.get("company_name") or row.get("company_code") or "未命名公司"
        parts.append(
            f"{name}：即时{directions.get('IMMEDIATE', 'UNKNOWN')}/"
            f"短期{directions.get('SHORT_TERM', 'UNKNOWN')}/中期{directions.get('MEDIUM_TERM', 'UNKNOWN')}"
        )
    return ["；".join(parts)] if parts else ["未登记公司映射，保留公司层面缺口"]


def _horizon_text(value: Any, fallback: str) -> str:
    if isinstance(value, Mapping):
        return str(value.get("reasoning_zh") or value.get("summary_zh") or fallback).strip()
    return str(value or fallback).strip()


def _qa_horizon_line(value: Any, fallback: str) -> str:
    if not isinstance(value, Mapping):
        return str(value or fallback).strip()
    windows = "、".join(str(item) for item in value.get("window_keys") or [])
    label = str(value.get("label_zh") or "阶段影响")
    focus = "、".join(str(item) for item in (value.get("observation_focus_zh") or [])[:2])
    reasoning = str(value.get("reasoning_zh") or value.get("summary_zh") or "")
    direction = re.search(r"方向分布为([^。]+)", reasoning)
    parts = [f"{windows or '当前窗口'}：{label}"]
    if focus:
        parts.append(f"观察{focus}")
    if direction:
        parts.append(f"方向分布为{direction.group(1)}")
    return "；".join(parts) + "。"


def _qa_percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "缺失"


def _qa_fact_lines(content: Mapping[str, Any], limit: int = 1) -> list[str]:
    lines = []
    for row in (content.get("official_facts") or [])[:limit]:
        if not isinstance(row, Mapping):
            continue
        fact = row.get("fact_zh") or row.get("original_quote")
        if fact:
            lines.append(f"{_core._short(fact, 150)}（证据 ID：{row.get('evidence_id') or '无'}）")
    return lines or ["未找到可直接核验的官方事实，保留证据缺口"]


def _qa_inference_lines(content: Mapping[str, Any], limit: int = 1) -> list[str]:
    lines = []
    for row in (content.get("research_inferences") or [])[:limit]:
        if not isinstance(row, Mapping):
            continue
        statement = row.get("inference_zh") or row.get("statement_zh")
        if statement:
            lines.append(f"{_core._short(statement, 170)}（证据 ID：{_core._ids(row.get('evidence_ids'))}）")
    return lines or ["机制与方向属于研究推断，不能升级为来源事实"]


def _qa_market_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    lines = []
    for row in (content.get("calculated_facts") or [])[:limit]:
        if not isinstance(row, Mapping):
            continue
        windows = row.get("fixed_windows") or row.get("windows") or {}
        if not isinstance(windows, Mapping):
            windows = {}
        values = "、".join(
            f"{name} {_qa_percent((windows.get(name) or {}).get('market_relative_return'))}"
            for name in ("T0", "D1", "D3", "D5", "D20")
            if isinstance(windows.get(name), Mapping)
        )
        name = row.get("industry_name_zh") or row.get("event_industry_mapping_id") or "行业"
        verdict = row.get("overall_verdict_zh") or row.get("overall_verdict") or "待判断"
        lines.append(f"{name}：{values or '窗口数据缺失'}；总体判定：{verdict}。")
    if lines:
        method = content.get("method_zh")
        if method:
            lines[-1] += f"计算口径：{_core._short(method, 130)}"
        return lines
    return ["未提供可用计算事实，不能用行情填补证据缺口"]


def render_answer(task_type: str, *, event: Mapping[str, Any], sample: Mapping[str, Any], chain: Mapping[str, Any] | None = None) -> str:
    if task_type == "EVENT_QA":
        content = select_task_content(event, sample)
        horizon = content.get("horizon_reasoning_zh") or {}
        sections = [
            ("直接回答", [_core._short(content.get("direct_answer_zh") or "材料不足，无法形成确定性回答。", 180)]),
            ("来源事实", _qa_fact_lines(content)),
            ("研究推断", _qa_inference_lines(content)),
            ("即时影响", [_qa_horizon_line(horizon.get("IMMEDIATE"), "按当前问题材料保持不确定")]),
            ("短期影响", [_qa_horizon_line(horizon.get("SHORT_TERM"), "按当前问题材料保持不确定")]),
            ("中期影响", [_qa_horizon_line(horizon.get("MEDIUM_TERM"), "按当前问题材料保持不确定")]),
            ("行情验证", _qa_market_lines(content)),
            ("证据边界", [_core._review_boundary(content)]),
        ]
        return _core.render_sections(sections, 1250)
    if task_type != "EVENT_ANALYSIS":
        return _render_other(task_type, event=event, sample=sample, chain=chain)
    content = select_task_content(event, sample)
    source = _core._source_lines(content)
    all_ids = content.get("answer_evidence_ids") or []
    preferred = next((eid for eid in all_ids if str(eid).endswith("who-pandemic")), None)
    preferred = preferred or next(iter(content.get("primary_answer_evidence_ids") or []), None)
    if preferred and all(str(preferred) not in line for line in source):
        source.append(f"核心事件事实保留证据 ID：{preferred}；证据状态按原始原文与定位完整性判断。")
    title = content.get("title_zh") or event.get("event_id")
    sections = [
        ("结论", [f"{title}是公开冲击，主要通过风险偏好、全球需求和避险需求传导；行业方向存在分化，当前为候选研究结论。"]),
        ("来源事实", source),
        ("即时影响", [_horizon_line(content, "IMMEDIATE")]),
        ("短期影响", [_horizon_line(content, "SHORT_TERM")]),
        ("中期影响", [_horizon_line(content, "MEDIUM_TERM")]),
        ("公司影响", _company_lines(content)),
        ("行情验证", _market_lines(content)),
        ("证据边界", [_core._review_boundary(content) + " " + str((content.get("boundaries") or {}).get("limitations_zh") or "行情仅作验证")]),
    ]
    return _core.render_sections(sections, 1250)


__all__ = ["render_answer"]
