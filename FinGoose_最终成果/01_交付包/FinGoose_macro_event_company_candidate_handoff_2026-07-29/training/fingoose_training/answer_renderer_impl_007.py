"""Render auditable market windows and causal abstention boundaries."""

from __future__ import annotations

from typing import Any, Mapping

from .answer_renderer_impl_006 import render_answer as _render_base
from .research_content import select_task_content


WINDOW_KEYS = ("T0", "D1", "D3", "D5", "D20")


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "缺失"


def _company_market_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    windows = content.get("relative_market_windows") or {}
    lines: list[str] = []
    for name in WINDOW_KEYS[:limit]:
        row = windows.get(name) or {}
        status = str(row.get("status") or "DATA_MISSING")
        if status in {"CALCULATED", "PARTIAL_CALCULATED"}:
            inputs = row.get("formula_inputs") or {}
            industry_relative = (
                _pct(row.get("industry_relative_return"))
                if row.get("industry_relative_return") is not None
                else f"缺失（{row.get('missing_reason') or 'INDUSTRY_BENCHMARK_MISSING'}）"
            )
            company_return = inputs.get("company_absolute_return")
            if company_return is None:
                company_return = row.get("company_absolute_return")
            lines.append(
                f"{name}：绝对收益 {_pct(company_return)}，"
                f"相对沪深300 {_pct(row.get('market_relative_return'))}，"
                f"相对行业 {industry_relative}；实际日期 {row.get('actual_date') or '缺失'}，"
                f"口径 {row.get('formula_version') or 'company-relative-v1'}，状态 {status}。"
            )
        else:
            lines.append(
                f"{name}：数据缺失（{row.get('missing_reason') or 'UNKNOWN'}），不以零值填补。"
            )
    return lines or ["公司相对收益窗口缺失，不以零值填补。"]


def _industry_market_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    market = content.get("market_window") or {}
    windows = market.get("fixed_windows") or {}
    lines: list[str] = []
    for name in WINDOW_KEYS[:limit]:
        row = windows.get(name) or {}
        if not row:
            lines.append(f"{name}：数据缺失，不以零值填补。")
            continue
        lines.append(
            f"{name}：行业收益 {_pct(row.get('industry_return'))}，"
            f"沪深300收益 {_pct(row.get('market_return'))}，"
            f"行业相对沪深300 {_pct(row.get('market_relative_return'))}；"
            f"实际日期 {row.get('actual_date') or '缺失'}。"
        )
    return lines or ["行业行情窗口缺失，不以零值填补。"]


def _causal_boundary(content: Mapping[str, Any]) -> str:
    causal = content.get("causal_identification") or {}
    status = causal.get("status") or "NOT_IDENTIFIED"
    conclusion = causal.get("causal_conclusion") or "ABSTAIN"
    unmet = "、".join(str(value) for value in causal.get("unmet_conditions") or [])
    return (
        f"因果识别：{status}；结论：{conclusion}；"
        f"未满足条件：{unmet or '无'}。"
        "行情只能验证机制一致性，不能把同期波动直接归因于宏观事件。"
    )


def _append_sections(base: str, sections: list[tuple[str, list[str]]]) -> str:
    blocks = [base.rstrip("。\n") + "。"]
    for heading, lines in sections:
        clean = [str(line).strip() for line in lines if str(line).strip()]
        blocks.append(heading + "：\n" + "\n".join(f"- {line}" for line in clean))
    answer = "\n".join(blocks)
    if len(answer) > 1250:
        compact = [blocks[0], *[block.splitlines()[0] + "\n" + block.splitlines()[1] for block in blocks[1:]]]
        answer = "\n".join(compact)
    return answer.rstrip("。\n") + "。"


def render_answer(
    task_type: str,
    *,
    event: Mapping[str, Any],
    sample: Mapping[str, Any],
    chain: Mapping[str, Any] | None = None,
) -> str:
    base = _render_base(task_type, event=event, sample=sample, chain=chain)
    content = select_task_content(event, sample)
    if task_type == "COMPANY_IMPACT":
        return _append_sections(
            base,
            [
                ("公司行情计算", _company_market_lines(content)),
                ("因果边界", [_causal_boundary(content)]),
            ],
        )
    if task_type == "INDUSTRY_IMPACT":
        return _append_sections(
            base,
            [
                ("行业行情计算", _industry_market_lines(content)),
                ("解释边界", ["机制一致性不等于因果关系。"]),
            ],
        )
    return base


__all__ = ["render_answer"]
