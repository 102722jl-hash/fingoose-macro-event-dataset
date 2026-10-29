"""Add Chinese evidence localization and concrete horizon narratives."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import fingoose_qa_reasoning_v2_impl_001 as _base


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
TIER_ZH = {
    "CORE_DIRECT": "直接影响",
    "SECOND_ORDER": "二阶传导",
    "CONDITIONAL": "条件性影响",
}
NODE_TYPE_ZH = {
    "EVENT_FACT": "事件事实",
    "BEHAVIOR_OR_POLICY_CHANGE": "行为或政策变化",
    "OBSERVABLE_DRIVER": "可观察驱动",
    "INDUSTRY_OPERATING_VARIABLE": "行业经营变量",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE": "行业收入或成本变量",
    "DIRECTION_ASSESSMENT": "方向研判",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE": "行情、混杂与反证",
}
HORIZON_ZH = {
    "IMMEDIATE": "即时",
    "SHORT_TERM": "短期",
    "MEDIUM_TERM": "中期",
}


def _localization(root: Path) -> dict[str, Any]:
    path = root / "configs/qa_reasoning_v2/qa_evidence_localization_zh.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _localize_evidence(
    evidence: Mapping[str, Any], localization: Mapping[str, Any]
) -> dict[str, Any]:
    row = dict(evidence)
    evidence_id = str(row["evidence_id"])
    facts = localization.get("evidence_facts") or {}
    if evidence_id not in facts:
        raise ValueError(f"MISSING_EVIDENCE_CHINESE_FACT:{evidence_id}")
    publisher = str(row.get("publisher") or row["evidence_id"])
    publishers = localization.get("publishers") or {}
    row["publisher_zh"] = publishers.get(publisher, publisher)
    row["fact_zh"] = str(facts[evidence_id])
    row["locator_zh"] = "官方页面对应引文段落；原始定位符见审计原文"
    row["translation_note_zh"] = "中文释义，英文原文保留用于审计"
    return row


def _direction_effect(direction: str) -> tuple[str, str]:
    return {
        "POSITIVE": ("改善或上升", "收入、利润率或现金流获得改善动力"),
        "NEGATIVE": ("回落或承压", "收入、利润率或现金流面临压力"),
        "MIXED": ("在子行业与公司之间分化", "收入、成本和利润的净效应分化"),
        "UNKNOWN": ("尚无法确认", "财务影响暂不作确定判断"),
    }.get(direction, ("尚无法确认", "财务影响暂不作确定判断"))


def _horizon_detail(impact: Mapping[str, Any], horizon: str) -> dict[str, str]:
    direction = str((impact.get("horizon_directions") or {}).get(horizon) or "UNKNOWN")
    direction_zh = DIRECTION_ZH.get(direction, "未知")
    driver = str(impact.get("observable_driver_zh") or "关键驱动")
    operating = str(impact.get("industry_operating_variable_zh") or "行业经营变量")
    financial = str(impact.get("industry_financial_variable_zh") or "行业财务变量")
    condition = str(impact.get("condition_zh") or "成立条件仍需核验")
    invalidation = str(
        impact.get("invalidation_condition_zh") or "失效条件仍需核验"
    )
    operating_effect, financial_effect = _direction_effect(direction)
    if horizon == "IMMEDIATE":
        detail = (
            f"事件首先作用于“{driver}”。在“{condition}”成立时，"
            f"“{operating}”将{operating_effect}，并使“{financial}”表现为："
            f"{financial_effect}。"
        )
    elif horizon == "SHORT_TERM":
        detail = (
            f"随着事件影响进入经营兑现期，重点跟踪“{driver}”。"
            f"“{operating}”预计{operating_effect}，继而使“{financial}”出现"
            f"{financial_effect}；前提是“{condition}”。"
        )
    else:
        detail = (
            f"中期净影响取决于“{condition}”能否持续。“{driver}”决定传导强度，"
            f"“{operating}”可能{operating_effect}，最终使“{financial}”呈现"
            f"{financial_effect}；若“{invalidation}”出现，当前方向需撤销或重估。"
        )
    return {
        "horizon_zh": HORIZON_ZH[horizon],
        "direction": direction,
        "direction_zh": direction_zh,
        "detail_zh": detail,
    }


def _enrich_impacts(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for impact in impacts:
        row = dict(impact)
        row["impact_tier_zh"] = TIER_ZH.get(
            str(row.get("impact_tier")), "影响层级待确认"
        )
        row["horizon_details"] = {
            horizon: _horizon_detail(row, horizon) for horizon in HORIZON_KEYS
        }
        enriched.append(row)
    return enriched


def _horizon_summary_zh(
    impacts: list[dict[str, Any]], horizon: str
) -> str:
    counts = Counter(
        str((row.get("horizon_directions") or {}).get(horizon) or "UNKNOWN")
        for row in impacts
    )
    examples: dict[str, list[str]] = {}
    for direction in ("POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"):
        examples[direction] = [
            str(row.get("industry_name_zh"))
            for row in impacts
            if (row.get("horizon_directions") or {}).get(horizon) == direction
        ][:2]
    parts = []
    for direction in ("POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"):
        count = counts.get(direction, 0)
        if not count:
            continue
        names = "、".join(examples[direction])
        suffix = f"，如{names}" if names else ""
        parts.append(f"{DIRECTION_ZH[direction]}{count}个{suffix}")
    drivers = "、".join(
        dict.fromkeys(
            str(row.get("observable_driver_zh"))
            for row in impacts
            if row.get("observable_driver_zh")
        )
    )
    driver_summary = "、".join(drivers.split("、")[:3])
    return (
        f"{HORIZON_ZH[horizon]}：{len(impacts)}个行业中"
        + "；".join(parts)
        + f"。重点观察{driver_summary}等驱动。"
    )


def _research_conclusion(
    chain: list[dict[str, Any]],
    impacts: list[dict[str, Any]],
    summaries: Mapping[str, str],
) -> str:
    behavior = next(
        (
            str(row.get("statement_zh"))
            for row in chain
            if row.get("node_type") == "BEHAVIOR_OR_POLICY_CHANGE"
        ),
        "事件通过行为、政策和价格变量向行业经营传导。",
    )
    tiers = {
        tier: "、".join(
            str(row.get("industry_name_zh"))
            for row in impacts
            if row.get("impact_tier") == tier
        )
        or "暂无"
        for tier in TIER_ZH
    }
    return (
        f"{behavior} 直接影响集中在{tiers['CORE_DIRECT']}；"
        f"二阶传导涉及{tiers['SECOND_ORDER']}；"
        f"条件性影响涉及{tiers['CONDITIONAL']}。"
        f"{summaries['IMMEDIATE']} {summaries['SHORT_TERM']} "
        f"{summaries['MEDIUM_TERM']}"
    )


def _enrich_answer(
    answer: Mapping[str, Any], localization: Mapping[str, Any]
) -> dict[str, Any]:
    row = dict(answer)
    evidence = [
        _localize_evidence(item, localization) for item in row.get("evidence") or []
    ]
    impacts = _enrich_impacts(list(row.get("industry_impacts") or []))
    chain = []
    for item in row.get("mechanism_chain") or []:
        node = dict(item)
        node["node_type_zh"] = NODE_TYPE_ZH.get(
            str(node.get("node_type")), "研究节点"
        )
        chain.append(node)
    summaries = {
        horizon: _horizon_summary_zh(impacts, horizon) for horizon in HORIZON_KEYS
    }
    conclusion = _research_conclusion(chain, impacts, summaries)
    layers = {key: dict(value) for key, value in row["answer_layers"].items()}
    layers["SOURCE_FACTS"]["evidence"] = evidence
    layers["RESEARCH_INFERENCE"].update(
        {
            "summary_zh": conclusion,
            "research_conclusion_zh": conclusion,
            "mechanism_chain": chain,
            "industry_impacts": impacts,
            "horizon_summary_zh": summaries,
        }
    )
    row.update(
        {
            "answer_layers": layers,
            "evidence": evidence,
            "mechanism_chain": chain,
            "industry_impacts": impacts,
            "horizon_summary_zh": summaries,
            "research_conclusion_zh": conclusion,
        }
    )
    if row.get("task_type") == "MAIN_REASONING":
        row["answer_focus_zh"] = conclusion
    return row


def build_qa_records(root: Path) -> QaBundle:
    root = root.resolve()
    bundle = _base.build_qa_records(root)
    localization = _localization(root)
    return QaBundle(
        cases=bundle.cases,
        answers=[_enrich_answer(row, localization) for row in bundle.answers],
        labels=bundle.labels,
    )


__all__ = [
    "ANSWER_LAYER_KEYS",
    "DIRECTION_ZH",
    "HORIZON_KEYS",
    "NODE_TYPE_ZH",
    "QaBundle",
    "TASK_LABELS",
    "TASK_TYPES",
    "TIER_ZH",
    "WINDOW_KEYS",
    "build_qa_records",
    "load_existing_source_fetches",
    "read_jsonl",
    "validate_qa_bundle",
    "write_candidate_package",
    "write_jsonl",
]
