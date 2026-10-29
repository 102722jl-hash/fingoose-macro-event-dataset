"""Render concise, evidence-linked Chinese answers from research content."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .research_content import HORIZONS, select_task_content

PLACEHOLDER_TOKENS = ("待补充陈述", '"nodes": [{}, {}', "omitted_count", "[嵌套内容省略]")


class AnswerRenderError(ValueError):
    """Raised when a required answer section has no content."""


def render_sections(sections: Sequence[tuple[str, Sequence[str]]], max_chars: int) -> str:
    blocks: list[str] = []
    for heading, lines in sections:
        clean = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
        if not clean:
            raise AnswerRenderError(f"empty required section: {heading}")
        block = heading + "：\n" + "\n".join(f"- {line}" for line in clean)
        blocks.append(block)
    answer = "\n".join(blocks).strip()
    if len(answer) > max_chars:
        # Keep section boundaries intact by dropping secondary bullets, never slicing JSON or text.
        compacted: list[str] = []
        for block in blocks:
            candidate = "\n".join([*compacted, block])
            if len(candidate) <= max_chars:
                compacted.append(block)
                continue
            heading, _, body = block.partition("：\n")
            first = body.splitlines()[0] if body else ""
            candidate = "\n".join([*compacted, heading + "：\n" + first])
            if len(candidate) <= max_chars:
                compacted.append(heading + "：\n" + first)
            else:
                raise AnswerRenderError(f"answer budget cannot fit required section: {heading}")
        answer = "\n".join(compacted)
    if not answer.endswith(("。", "。\n")):
        answer += "。"
    return answer


def _short(value: Any, limit: int = 150) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "。"


def _ids(values: Any, limit: int = 3) -> str:
    if not isinstance(values, list):
        return "无"
    clean = [str(value) for value in values if value]
    return "、".join(clean[:limit]) or "无"


def _review_boundary(content: Mapping[str, Any]) -> str:
    review = str(content.get("review_status") or "NEEDS_HUMAN_REVIEW")
    formal_ready = bool(content.get("formal_ready", False))
    causal = content.get("causal_attribution_allowed")
    parts = []
    if not formal_ready or "REVIEW" in review.upper():
        parts.append("该记录仍为候选数据，待人工审核")
    if causal is False:
        parts.append("当前材料不允许确定性因果归因")
    return "；".join(parts) + "。" if parts else "证据边界需继续核验。"


def _event_content(event: Mapping[str, Any]) -> Mapping[str, Any]:
    return event.get("research_content") or {}


def _source_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    lines = []
    for fact in (content.get("source_facts") or [])[:limit]:
        lines.append(
            f"{_short(fact.get('statement_zh'), 125)}（证据 ID：{_ids(fact.get('evidence_ids'))}；状态：{fact.get('evidence_status') or '待核验'}）"
        )
    return lines


def _horizon_line(content: Mapping[str, Any], horizon: str) -> str:
    block = (content.get("horizon_analysis") or {}).get(horizon) or {}
    summary = _short(block.get("summary_zh"), 300)
    return f"{summary} 证据 ID：{_ids(block.get('evidence_ids'), 4)}。"


def _market_lines(content: Mapping[str, Any], limit: int = 2) -> list[str]:
    rows = content.get("market_validation") or []
    if isinstance(rows, Mapping):
        rows = [rows]
    lines = []
    for row in list(rows)[:limit]:
        if not isinstance(row, Mapping):
            continue
        asset = row.get("series_id") or row.get("industry_name_zh") or row.get("market_benchmark") or "市场窗口"
        status = row.get("window_status") or row.get("data_availability_gap") or "DATA_PENDING"
        windows = row.get("fixed_windows") or row.get("windows") or {}
        available = [name for name in ("T0", "D1", "D3", "D5", "D20") if isinstance(windows, Mapping) and windows.get(name)]
        lines.append(f"{asset}：窗口 {','.join(available) or '缺数据'}，状态 {status}；只用于验证同步反应，不证明严格因果")
    return lines or ["未提供可用行情窗口，保留 DATA_PENDING，不将缺失写成零"]


def _event_answer(event: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    title = content.get("title_zh") or event.get("title_zh") or event.get("event_id")
    conclusion = f"{title}是公开冲击，主要通过风险偏好、全球需求和避险需求传导；行业方向存在分化，当前为候选研究结论。"
    sections = [
        ("结论", [conclusion]),
        ("来源事实", _source_lines(content)),
        ("即时影响", [_horizon_line(content, "IMMEDIATE")]),
        ("短期影响", [_horizon_line(content, "SHORT_TERM")]),
        ("中期影响", [_horizon_line(content, "MEDIUM_TERM")]),
        ("行情验证", _market_lines(content)),
        ("证据边界", [_review_boundary(content) + " " + str((content.get("boundaries") or {}).get("limitations_zh") or "行情仅作验证")]),
    ]
    return render_sections(sections, 1250)


def _industry_answer(event: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    name = content.get("industry_name_zh") or "当前行业"
    nodes = content.get("mechanism_nodes") or []
    mechanism = [f"第{i}步：{_short(node.get('statement_zh'), 130)}" for i, node in enumerate(nodes[:7], 1) if node.get("statement_zh")]
    if len(mechanism) < 3:
        mechanism.append("机制链证据不足，方向保持候选")
    directions = content.get("horizon_directions") or {}
    market = content.get("market_window") or {}
    sections = [
        ("结论", [f"{name}：事件冲击下即时{directions.get('IMMEDIATE', 'UNKNOWN')}、短期{directions.get('SHORT_TERM', 'UNKNOWN')}、中期{directions.get('MEDIUM_TERM', 'UNKNOWN')}，结论仍为候选。"]),
        ("事件事实", [f"事件事实通过证据 ID {_ids(content.get('evidence_ids'), 4)} 关联；当前行业不等同于单一公司的方向。"]),
        ("七步机制", mechanism),
        ("即时影响", [f"方向为 {directions.get('IMMEDIATE', 'UNKNOWN')}，观察 {_short(content.get('observable_driver_zh'), 100)}。"]),
        ("短期影响", [f"方向为 {directions.get('SHORT_TERM', 'UNKNOWN')}，条件是 {_short(content.get('condition_zh'), 130)}。"]),
        ("中期影响", [f"方向为 {directions.get('MEDIUM_TERM', 'UNKNOWN')}，需关注 {_short(content.get('invalidation_condition_zh'), 130)}。"]),
        ("经营变量", [_short(content.get('industry_operating_variable_zh'), 170)]),
        ("财务变量", [_short(content.get('industry_financial_variable_zh'), 170)]),
        ("行情验证", _market_lines({"market_validation": [market]})),
        ("失效条件和证据边界", [_short(content.get('invalidation_condition_zh'), 180) + "；" + _review_boundary(content)]),
    ]
    return render_sections(sections, 1250)


def _company_answer(event: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    name = content.get("company_name") or content.get("company_code") or "当前公司"
    directions = content.get("horizon_directions") or {}
    sections = [
        ("结论", [f"{name}的业务暴露决定其与行业冲击并不等同；即时{directions.get('IMMEDIATE', 'UNKNOWN')}、短期{directions.get('SHORT_TERM', 'UNKNOWN')}、中期{directions.get('MEDIUM_TERM', 'UNKNOWN')}，结论为候选。"]),
        ("业务暴露", [_short(content.get('business_exposure_zh'), 180)]),
        ("经营路径", [_short(content.get('mechanism_zh'), 200)]),
        ("即时影响", [f"方向为 {directions.get('IMMEDIATE', 'UNKNOWN')}。"]),
        ("短期影响", [f"方向为 {directions.get('SHORT_TERM', 'UNKNOWN')}，条件：{_short((content.get('conditions') or ['未提供'])[0], 120)}。"]),
        ("中期影响", [f"方向为 {directions.get('MEDIUM_TERM', 'UNKNOWN')}，失效条件：{_short((content.get('invalidation_conditions') or ['未提供'])[0], 120)}。"]),
        ("公司行情", _market_lines({"market_validation": [content.get("market_window") or {}]})),
        ("混杂因素与反证", [_short(content.get('confounder_argument_zh') or (content.get('counterevidence') or [{}])[0].get('claim_zh'), 180)]),
        ("审核状态和因果边界", [_review_boundary(content)]),
    ]
    return render_sections(sections, 1250)


def _qa_answer(event: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    direct = _short(content.get("direct_answer_zh") or "材料不足，无法形成确定性回答。", 300)
    task_type = str(content.get("task_type") or "").upper()
    facts = content.get("official_facts") or []
    inferences = content.get("research_inferences") or []
    calculated = content.get("calculated_facts") or []
    fact_lines = [f"{_short(row.get('fact_zh') or row.get('original_quote'), 130)}（证据 ID：{row.get('evidence_id') or '无'}）" for row in facts[:2] if isinstance(row, Mapping)]
    if not fact_lines:
        fact_lines = ["未找到可直接核验的官方事实，保留证据缺口"]
    inference_lines = [f"{_short(row.get('inference_zh') or row.get('statement_zh'), 150)}（证据 ID：{_ids(row.get('evidence_ids'))}）" for row in inferences[:2] if isinstance(row, Mapping)]
    if not inference_lines:
        inference_lines = ["机制与方向属于研究推断，不能升级为来源事实"]
    calc_lines = ["已提供计算窗口，行情只用于验证，不单独证明因果。" if calculated else "未提供可用计算事实，不能用行情填补证据缺口"]
    sections = [
        ("直接回答", [direct]),
        ("来源事实", fact_lines),
        ("研究推断", inference_lines),
        ("即时影响", [_short((content.get('horizon_reasoning_zh') or {}).get('IMMEDIATE') or "按当前问题材料保持不确定", 180)]),
        ("短期影响", [_short((content.get('horizon_reasoning_zh') or {}).get('SHORT_TERM') or "按当前问题材料保持不确定", 180)]),
        ("中期影响", [_short((content.get('horizon_reasoning_zh') or {}).get('MEDIUM_TERM') or "按当前问题材料保持不确定", 180)]),
        ("行情验证", calc_lines),
        ("证据边界", [_review_boundary(content)]),
    ]
    return render_sections(sections, 1250)


def render_answer(task_type: str, *, event: Mapping[str, Any], sample: Mapping[str, Any], chain: Mapping[str, Any] | None = None) -> str:
    content = select_task_content(event, sample)
    if task_type == "EVENT_ANALYSIS":
        return _event_answer(event, content)
    if task_type == "INDUSTRY_IMPACT":
        return _industry_answer(event, content)
    if task_type == "COMPANY_IMPACT":
        return _company_answer(event, content)
    if task_type == "EVENT_QA":
        return _qa_answer(event, content)
    raise AnswerRenderError(f"unsupported task_type={task_type}")


__all__ = ["AnswerRenderError", "PLACEHOLDER_TOKENS", "render_answer", "render_sections"]
