"""Build task-specific Q&A answers and time-specific horizon reasoning."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import fingoose_qa_reasoning_v2_impl_002 as _base
from fingoose_company_impact_ui_v2 import build_ui_bundle as build_company_ui_bundle


ANSWER_LAYER_KEYS = _base.ANSWER_LAYER_KEYS
HORIZON_KEYS = _base.HORIZON_KEYS
QaBundle = _base.QaBundle
TASK_LABELS = _base.TASK_LABELS
TASK_TYPES = _base.TASK_TYPES
WINDOW_KEYS = _base.WINDOW_KEYS
load_existing_source_fetches = _base.load_existing_source_fetches
read_jsonl = _base.read_jsonl
validate_qa_bundle = _base.validate_qa_bundle
write_candidate_package = _base.write_candidate_package
write_jsonl = _base.write_jsonl


DIRECTION_ZH = {
    "POSITIVE": "正向",
    "NEGATIVE": "负向",
    "MIXED": "分化",
    "UNKNOWN": "未知",
}
VERDICT_ZH = {
    "SUPPORTS": "支持",
    "WEAKENS": "削弱",
    "INDISTINGUISHABLE": "无法区分",
    "DATA_MISSING": "数据缺失",
}
HORIZON_WINDOW_KEYS = {
    "IMMEDIATE": ("T0", "D1"),
    "SHORT_TERM": ("D3", "D5"),
    "MEDIUM_TERM": ("D20",),
}
HORIZON_LABELS = {
    "IMMEDIATE": "即时",
    "SHORT_TERM": "短期",
    "MEDIUM_TERM": "中期",
}


def _unique_text(rows: Iterable[Mapping[str, Any]], key: str, limit: int = 3) -> list[str]:
    values: list[str] = []
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
        if len(values) == limit:
            break
    return values


def _direction_breakdown(impacts: list[dict[str, Any]], horizon: str) -> str:
    counts = Counter(
        str((row.get("horizon_directions") or {}).get(horizon) or "UNKNOWN")
        for row in impacts
    )
    parts = [
        f"{DIRECTION_ZH[key]}{counts[key]}个"
        for key in ("POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN")
        if counts[key]
    ]
    examples = []
    for direction in ("POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"):
        names = [
            str(row.get("industry_name_zh"))
            for row in impacts
            if (row.get("horizon_directions") or {}).get(horizon) == direction
        ][:2]
        if names:
            examples.append(f"{DIRECTION_ZH[direction]}：{'、'.join(names)}")
    return f"方向分布为{'、'.join(parts)}；代表行业为{'；'.join(examples)}。"


def _horizon_reasoning(impacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    immediate_focus = _unique_text(impacts, "observable_driver_zh")
    short_focus = _unique_text(impacts, "industry_operating_variable_zh")
    medium_focus = _unique_text(impacts, "industry_financial_variable_zh")
    immediate = (
        "即时（T0、D1）看事件公开后的首轮预期重估与交易反应，"
        f"先观察{'、'.join(immediate_focus)}。{_direction_breakdown(impacts, 'IMMEDIATE')}"
        "这一段回答市场和经营主体最先改变了什么，不把后续经营结果提前写入。"
    )
    short = (
        "短期（D3、D5）看预期是否进入经营兑现与连续反馈，"
        f"重点核验{'、'.join(short_focus)}。{_direction_breakdown(impacts, 'SHORT_TERM')}"
        "这一段回答订单、客流、开工、库存或成本是否已经沿传导链发生变化。"
    )
    medium = (
        "中期（D20）看冲击能否持续并形成供需、产能或竞争结构变化，"
        f"重点核验{'、'.join(medium_focus)}。{_direction_breakdown(impacts, 'MEDIUM_TERM')}"
        "这一段回答收入、利润率、现金流及需求结构是否延续，并检查失效条件。"
    )
    return {
        "IMMEDIATE": {
            "label_zh": "首轮预期与交易反应",
            "window_keys": ["T0", "D1"],
            "observation_focus_zh": immediate_focus,
            "reasoning_zh": immediate,
        },
        "SHORT_TERM": {
            "label_zh": "经营兑现与反馈",
            "window_keys": ["D3", "D5"],
            "observation_focus_zh": short_focus,
            "reasoning_zh": short,
        },
        "MEDIUM_TERM": {
            "label_zh": "持续性与结构变化",
            "window_keys": ["D20"],
            "observation_focus_zh": medium_focus,
            "reasoning_zh": medium,
        },
    }


def _evidence_audit(answer: Mapping[str, Any]) -> dict[str, Any]:
    official_facts = [dict(row) for row in answer.get("evidence") or []]
    research_inferences = [
        {
            "step": row.get("step"),
            "type_zh": row.get("node_type_zh"),
            "inference_zh": row.get("statement_zh"),
            "evidence_ids": list(row.get("evidence_ids") or []),
        }
        for row in answer.get("mechanism_chain") or []
        if row.get("node_type") != "EVENT_FACT"
    ]
    calculated_facts = []
    for row in answer.get("market_windows") or []:
        calculated_facts.append(
            {
                "event_industry_mapping_id": row.get("event_industry_mapping_id"),
                "industry_name_zh": row.get("industry_name_zh"),
                "window_status": row.get("window_status"),
                "formula_zh": "行业相对收益 = 行业收益 - 沪深300收益",
                "windows": dict(row.get("fixed_windows") or {}),
            }
        )
    refusals = [dict(row) for row in answer.get("refusals") or []]
    return {
        "answer_type": "EVIDENCE_AUDIT",
        "direct_answer_zh": (
            f"结论分类：官方事实 {len(official_facts)} 条；研究推断 {len(research_inferences)} 条；"
            f"计算事实 {len(calculated_facts)} 组；拒答边界 {len(refusals)} 项。"
            "只有官方原文直接支持的内容列为事实，机制与方向均明确列为研究推断。"
        ),
        "official_facts": official_facts,
        "research_inferences": research_inferences,
        "calculated_facts": calculated_facts,
        "refusal_boundaries": refusals,
    }


def _mean_relative(windows: Mapping[str, Any], keys: Iterable[str]) -> float | None:
    values = []
    for key in keys:
        point = windows.get(key) or {}
        value = point.get("market_relative_return")
        if value is None:
            return None
        values.append(float(value))
    return sum(values) / len(values) if values else None


def _market_verdict(
    direction: str,
    windows: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    cutoff_blocked: bool,
) -> dict[str, Any]:
    if cutoff_blocked:
        verdict = "INDISTINGUISHABLE"
        basis = "事件锚点晚于截止日，不能用截止日后行情回填预测判断。"
        mean = None
    else:
        mean = _mean_relative(windows, keys)
        if mean is None:
            verdict = "DATA_MISSING"
            basis = f"{'+'.join(keys)} 存在缺失值，保持为空且不补零。"
        elif direction not in {"POSITIVE", "NEGATIVE"} or mean == 0:
            verdict = "INDISTINGUISHABLE"
            basis = (
                f"预设方向为{DIRECTION_ZH.get(direction, '未知')}，"
                f"{'+'.join(keys)} 平均相对收益为 {mean:.2%}，不能作同向或反向区分。"
            )
        else:
            supports = (direction == "POSITIVE" and mean > 0) or (
                direction == "NEGATIVE" and mean < 0
            )
            verdict = "SUPPORTS" if supports else "WEAKENS"
            relation = "同向" if supports else "反向"
            basis = (
                f"预设方向为{DIRECTION_ZH[direction]}，{'+'.join(keys)} "
                f"平均相对收益为 {mean:.2%}，与预设方向{relation}。"
            )
    return {
        "verdict": verdict,
        "verdict_zh": VERDICT_ZH[verdict],
        "mean_market_relative_return": mean,
        "basis_zh": basis,
    }


def _overall_verdict(verdicts: Mapping[str, Mapping[str, Any]]) -> str:
    values = [str(row["verdict"]) for row in verdicts.values()]
    if "WEAKENS" in values and "SUPPORTS" not in values:
        return "WEAKENS"
    if "SUPPORTS" in values and "WEAKENS" not in values:
        return "SUPPORTS"
    if values and all(value == "DATA_MISSING" for value in values):
        return "DATA_MISSING"
    return "INDISTINGUISHABLE"


def _market_validation(answer: Mapping[str, Any]) -> dict[str, Any]:
    impacts = {
        str(row.get("event_industry_mapping_id")): row
        for row in answer.get("industry_impacts") or []
    }
    cutoff_blocked = any(
        row.get("refusal_reason") == "ANCHOR_POST_CUTOFF"
        for row in answer.get("refusals") or []
    )
    industry_results = []
    for market_row in answer.get("market_windows") or []:
        mapping_id = str(market_row.get("event_industry_mapping_id"))
        impact = impacts.get(mapping_id, {})
        source_windows = market_row.get("fixed_windows") or {}
        windows = {key: dict(source_windows.get(key) or {}) for key in WINDOW_KEYS}
        verdicts = {
            horizon: _market_verdict(
                str((impact.get("horizon_directions") or {}).get(horizon) or "UNKNOWN"),
                windows,
                HORIZON_WINDOW_KEYS[horizon],
                cutoff_blocked=cutoff_blocked,
            )
            for horizon in HORIZON_KEYS
        }
        overall = "INDISTINGUISHABLE" if cutoff_blocked else _overall_verdict(verdicts)
        industry_results.append(
            {
                "event_industry_mapping_id": mapping_id,
                "industry_name_zh": market_row.get("industry_name_zh"),
                "expected_directions": dict(impact.get("horizon_directions") or {}),
                "windows": windows,
                "horizon_verdicts": verdicts,
                "overall_verdict": overall,
                "overall_verdict_zh": VERDICT_ZH[overall],
            }
        )
    counts = Counter(row["overall_verdict"] for row in industry_results)
    if cutoff_blocked:
        direct = "事件锚点晚于截止日，行情不得用于验证该锚点；以下窗口仅保留为计算展示，统一判为无法区分。"
    else:
        direct = (
            f"行情验证覆盖 {len(industry_results)} 个行业：支持 {counts['SUPPORTS']} 个、"
            f"削弱 {counts['WEAKENS']} 个、无法区分 {counts['INDISTINGUISHABLE']} 个、"
            f"数据缺失 {counts['DATA_MISSING']} 个。结论只检验机制一致性，不证明因果。"
        )
    return {
        "answer_type": "MARKET_VALIDATION",
        "direct_answer_zh": direct,
        "method_zh": (
            "以 T-1 为共同基期，逐窗计算行业收益、沪深300收益与相对收益；"
            "即时使用 T0+D1，短期使用 D3+D5，中期使用 D20。"
        ),
        "cutoff_blocked": cutoff_blocked,
        "industry_results": industry_results,
    }


def _public_disclosure(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": row.get("evidence_id"),
        "claim_type": row.get("claim_type"),
        "document_title": row.get("document_title"),
        "published_at": row.get("published_at"),
        "original_quote": row.get("original_quote"),
        "locator_zh": row.get("page_or_section_locator"),
        "source_url": row.get("source_url"),
        "review_status": row.get("review_status"),
    }


def _company_result(company: Mapping[str, Any], cutoff_date: str) -> dict[str, Any]:
    priority = {
        "BUSINESS_EXPOSURE": 0,
        "GEOGRAPHIC_EXPOSURE": 1,
        "DEMAND_COST_EXPOSURE": 2,
    }
    evidence = [
        row
        for row in company.get("evidence") or []
        if row.get("claim_type") in priority
        and str(row.get("published_at") or "9999-99-99") <= cutoff_date
    ]
    evidence.sort(
        key=lambda row: (
            priority[str(row.get("claim_type"))],
            str(row.get("published_at") or ""),
        )
    )
    limitation_evidence = [
        _public_disclosure(row)
        for row in company.get("evidence") or []
        if row.get("claim_type") == "LIMITATION_OR_COUNTEREVIDENCE"
        and str(row.get("published_at") or "9999-99-99") <= cutoff_date
    ]
    direction = company.get("direction") or {}
    confounder_bundle = company.get("confounders") or {}
    registered = confounder_bundle.get("registered_confounders") or []
    confounders = [
        {
            "title_zh": row.get("announcement_title") or "独立公司事项",
            "type": row.get("confounder_type"),
            "first_public_at": row.get("first_public_at"),
            "affected_windows": list(row.get("affected_windows") or []),
            "mechanism_zh": row.get("mechanism_zh"),
            "original_quote": row.get("original_quote"),
            "source_url": row.get("source_url"),
        }
        for row in registered
    ]
    counter_review = company.get("counterevidence_review") or {}
    counterevidence = limitation_evidence + [
        dict(row) for row in counter_review.get("findings") or []
    ]
    search = company.get("confounder_search_audit") or {}
    trading = company.get("trading_status_review") or {}
    overall_trading = str(trading.get("overall_status") or "UNVERIFIED")
    trading_zh = {
        "VERIFIED_TRADING": "正常交易已核验",
        "VERIFIED_SUSPENDED": "停牌已核验",
    }.get(overall_trading, "交易状态尚未核验")
    suspension = str(confounder_bundle.get("suspension_status") or overall_trading)
    suspension_zh = {
        "VERIFIED_TRADING": "六个窗口未显示停牌，正常交易",
        "VERIFIED_SUSPENDED": "已核验存在停牌",
    }.get(suspension, "停复牌状态待核验")
    completion = str((company.get("completion") or {}).get("completion_status") or "OPEN")
    decision = (
        "证据链可用于条件性公司影响候选，但仍需人工复核，且不得将行情变化作单一因果归因。"
        if completion != "OPEN"
        else "公司证据闭环仍为 OPEN，仅保留条件性机制与拒答边界，不给出确定性归因。"
    )
    directions = {
        horizon: DIRECTION_ZH.get(
            str((direction.get("horizons") or {}).get(horizon) or "UNKNOWN"), "未知"
        )
        for horizon in HORIZON_KEYS
    }
    return {
        "company_name": company.get("company_name"),
        "company_code": company.get("company_code"),
        "industry_name_zh": company.get("industry"),
        "pre_event_disclosures": [_public_disclosure(row) for row in evidence],
        "mechanism_zh": direction.get("mechanism") or "公司层机制尚待人工复核。",
        "directions_zh": directions,
        "conditions_zh": list(direction.get("conditions") or []),
        "invalidation_conditions_zh": list(direction.get("invalidation_conditions") or []),
        "counterevidence": counterevidence,
        "counterevidence_search_zh": (
            f"已检索 {search.get('title_count', 0)} 条官方公告标题，"
            f"正文复核 {search.get('body_reviewed_count', 0)} 条；"
            f"检索状态为 {search.get('search_status') or '待核验'}。"
        ),
        "confounders": confounders,
        "trading_status_zh": trading_zh,
        "suspension_status_zh": suspension_zh,
        "decision_zh": decision,
    }


def _industry_company(
    answer: Mapping[str, Any], event: Mapping[str, Any]
) -> dict[str, Any]:
    cutoff_date = str(answer.get("prediction_cutoff_at"))[:10]
    results = [_company_result(row, cutoff_date) for row in event.get("companies") or []]
    names = "、".join(str(row["company_name"]) for row in results)
    return {
        "answer_type": "INDUSTRY_COMPANY",
        "direct_answer_zh": (
            f"本事件沿行业机制核查 {len(results)} 家公司：{names}。"
            "每家公司分别给出事件前业务披露、传导机制、三阶段方向、成立与失效条件、"
            "反证、独立混杂及停复牌核验，不以行业方向自动替代公司结论。"
        ),
        "company_results": results,
    }


def _enrich_answer(
    answer: Mapping[str, Any], event: Mapping[str, Any]
) -> dict[str, Any]:
    row = dict(answer)
    reasoning = _horizon_reasoning(list(row.get("industry_impacts") or []))
    row["horizon_reasoning_zh"] = reasoning
    row["horizon_summary_zh"] = {
        horizon: reasoning[horizon]["reasoning_zh"] for horizon in HORIZON_KEYS
    }
    if row.get("task_type") == "MAIN_REASONING":
        row["answer_focus_zh"] = " ".join(
            reasoning[horizon]["reasoning_zh"] for horizon in HORIZON_KEYS
        )
    elif row.get("task_type") == "EVIDENCE_AUDIT":
        row["task_answer"] = _evidence_audit(row)
        row["answer_focus_zh"] = row["task_answer"]["direct_answer_zh"]
    elif row.get("task_type") == "MARKET_VALIDATION":
        row["task_answer"] = _market_validation(row)
        row["answer_focus_zh"] = row["task_answer"]["direct_answer_zh"]
    elif row.get("task_type") == "INDUSTRY_COMPANY":
        row["task_answer"] = _industry_company(row, event)
        row["answer_focus_zh"] = row["task_answer"]["direct_answer_zh"]
    return row


def build_qa_records(root: Path) -> QaBundle:
    root = root.resolve()
    bundle = _base.build_qa_records(root)
    company_bundle = build_company_ui_bundle(root)
    events = {str(row["event_id"]): row for row in company_bundle["events"]}
    return QaBundle(
        cases=bundle.cases,
        answers=[
            _enrich_answer(row, events[str(row["event_id"])]) for row in bundle.answers
        ],
        labels=bundle.labels,
    )


__all__ = [
    "ANSWER_LAYER_KEYS",
    "DIRECTION_ZH",
    "HORIZON_KEYS",
    "QaBundle",
    "TASK_LABELS",
    "TASK_TYPES",
    "VERDICT_ZH",
    "WINDOW_KEYS",
    "build_qa_records",
    "load_existing_source_fetches",
    "read_jsonl",
    "validate_qa_bundle",
    "write_candidate_package",
    "write_jsonl",
]
