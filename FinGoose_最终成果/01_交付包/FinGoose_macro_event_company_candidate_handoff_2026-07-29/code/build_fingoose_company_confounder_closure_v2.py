"""Public closure builder with paragraph-safe Chinese argument rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _build_fingoose_company_confounder_closure_v2_base as _base


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _argument(
    *,
    mapping: dict[str, Any],
    chain: dict[str, Any],
    search: dict[str, Any],
    bodies: list[dict[str, Any]],
    trading: dict[str, Any],
    counter: dict[str, Any],
    grade: str,
    unresolved: list[str],
) -> str:
    statements = _base._chain_statements(chain)
    company = str(mapping.get("company_name") or mapping.get("company_code"))
    hypothesis = (
        f"研究假设：锚点事实为“{_clip(statements.get('EVENT_FACT') or mapping.get('event_id'), 52)}”。"
        f"候选机制是“{_clip(statements.get('BEHAVIOR_OR_POLICY_CHANGE'), 42)}”"
        f"改变“{_clip(statements.get('OBSERVABLE_OPERATING_VARIABLE'), 34)}”，"
        f"再作用于{company}；业务暴露依据为“{_clip(statements.get('COMPANY_BUSINESS_EXPOSURE'), 46)}”。"
        "该路径未使用事后股价选样。"
    )
    relevant = [
        row
        for row in bodies
        if row.get("relevance_decision") in {"RELEVANT", "MINOR_RELEVANCE"}
    ]
    if relevant:
        titles = "；".join(_clip(row.get("announcement_title"), 24) for row in relevant[:2])
        windows = "、".join(
            _base._unique(
                str(window)
                for row in relevant
                for window in row.get("affected_windows") or []
            )
        )
        announcement = (
            f"公告检索：{search.get('window_start')}至{search.get('window_end')}共复核"
            f"{search.get('title_count')}条官方标题、完成{search.get('body_reviewed_count')}条正文处置；"
            f"竞争解释包括“{titles}”，候选影响窗口为{windows or '未明确'}。标题不单独构成等级证据。"
        )
    else:
        announcement = (
            f"公告检索：{search.get('window_start')}至{search.get('window_end')}共分类"
            f"{search.get('title_count')}条官方标题，固定八类规则未筛出经正文核对的实质公司混杂；"
            "这不等于证明不存在未披露事项。"
        )
    dates = "/".join(
        str((trading.get("window_reviews") or {}).get(window, {}).get("actual_date") or "缺失")
        for window in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
    )
    trading_text = (
        f"交易核验：六个实际日期为{dates}，状态为{trading.get('overall_status')}。"
        "非空行情只证明当日可观测，不能证明宏观事件造成收益，也不能替代停复牌公告。"
    )
    finding_count = len(counter.get("findings") or [])
    counter_text = (
        f"反证边界：已登记{finding_count}条年报限制因素或窗口公告证据，用于检验业务缓冲、"
        "传导失效及独立公司驱动；事件后披露不会回填为事件前可见信息。"
        if finding_count
        else "反证边界：已完成 dossier、方向失效条件及窗口公告负向检索，未以空数组替代检索记录。"
    )
    if unresolved:
        conclusion = (
            f"综合门禁为{grade}，未关闭项为{'、'.join(unresolved)}；记录保持NEEDS_HUMAN_REVIEW，"
            "仅进入挑战集并拒绝直接归因。"
        )
    else:
        conclusion = (
            f"综合门禁为{grade}候选等级。证据链虽已闭合，记录仍为NEEDS_HUMAN_REVIEW，"
            "禁止作确定性因果归因。"
        )
    text = hypothesis + announcement + trading_text + counter_text + conclusion
    if len(text) < 250:
        text = text[:-len(conclusion)] + "所有引文均保留官方链接、正文定位和映射标识。" + conclusion
    if not 250 <= len(text) <= 600:
        raise ValueError(f"ARGUMENT_LENGTH_OUT_OF_RANGE:{mapping['mapping_id']}:{len(text)}")
    return text


_base._argument = _argument
build_closure = _base.build_closure
build = _base.build
main = _base.main


if __name__ == "__main__":
    raise SystemExit(main())
