"""Add evidence lineage, market strength, and company selection reasons."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

import fingoose_qa_reasoning_v2_impl_004 as _base
from fingoose_company_impact_ui_v2 import build_ui_bundle as build_company_ui_bundle


ANSWER_LAYER_KEYS = _base.ANSWER_LAYER_KEYS
DIRECTION_ZH = _base.DIRECTION_ZH
HORIZON_KEYS = _base.HORIZON_KEYS
QaBundle = _base.QaBundle
TASK_LABELS = _base.TASK_LABELS
TASK_TYPES = _base.TASK_TYPES
VERDICT_ZH = _base.VERDICT_ZH
WINDOW_KEYS = _base.WINDOW_KEYS
load_existing_source_fetches = _base.load_existing_source_fetches
read_jsonl = _base.read_jsonl
validate_qa_bundle = _base.validate_qa_bundle
write_candidate_package = _base.write_candidate_package
write_jsonl = _base.write_jsonl


def _flatten_evidence_ids(impact: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    chain = impact.get("mechanism_chain") or {}
    for node in chain.get("nodes") or []:
        for evidence_id in node.get("evidence_ids") or []:
            if evidence_id and evidence_id not in values:
                values.append(str(evidence_id))
    for evidence_id in impact.get("event_evidence_ids") or []:
        if evidence_id and evidence_id not in values:
            values.append(str(evidence_id))
    return values


def _ids_for_node_types(impact: Mapping[str, Any], node_types: set[str]) -> list[str]:
    values: list[str] = []
    chain = impact.get("mechanism_chain") or {}
    for node in chain.get("nodes") or []:
        if node.get("node_type") not in node_types:
            continue
        for evidence_id in node.get("evidence_ids") or []:
            if evidence_id and evidence_id not in values:
                values.append(str(evidence_id))
    return values or _flatten_evidence_ids(impact)


def _add_lineage(
    answer: dict[str, Any], raw_event: Mapping[str, Any]
) -> None:
    raw_impacts = {
        str(row.get("event_industry_mapping_id")): row
        for row in raw_event.get("industry_impacts") or []
    }
    fallback = [str(row.get("evidence_id")) for row in answer.get("evidence") or []]
    for impact in answer.get("industry_impacts") or []:
        raw = raw_impacts.get(str(impact.get("event_industry_mapping_id")), {})
        evidence_ids = _flatten_evidence_ids(raw) or fallback[:3]
        impact["research_evidence_ids"] = evidence_ids
        impact["evidence_lineage_zh"] = (
            f"该行业推断绑定 {len(evidence_ids)} 条事件/机制证据；"
            "证据不足时仍保持候选状态，不补造事实。"
        )
    for horizon, row in (answer.get("horizon_reasoning_zh") or {}).items():
        type_map = {
            "IMMEDIATE": {"EVENT_FACT", "BEHAVIOR_OR_POLICY_CHANGE"},
            "SHORT_TERM": {"OBSERVABLE_DRIVER", "INDUSTRY_OPERATING_VARIABLE"},
            "MEDIUM_TERM": {
                "INDUSTRY_REVENUE_OR_COST_VARIABLE",
                "DIRECTION_ASSESSMENT",
                "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
            },
        }
        ids: list[str] = []
        for raw in raw_event.get("industry_impacts") or []:
            for evidence_id in _ids_for_node_types(raw, type_map.get(horizon, set())):
                if evidence_id not in ids:
                    ids.append(evidence_id)
        row["evidence_ids"] = ids or fallback[:3]


def _add_market_strength(answer: dict[str, Any]) -> None:
    for result in (answer.get("task_answer") or {}).get("industry_results") or []:
        for verdict in (result.get("horizon_verdicts") or {}).values():
            mean = verdict.get("mean_market_relative_return")
            if mean is None:
                strength = "NOT_ASSESSABLE"
                strength_zh = "不可评估"
            elif abs(float(mean)) < 0.02:
                strength = "WEAK"
                strength_zh = "统计偏弱"
            elif abs(float(mean)) < 0.05:
                strength = "MODERATE"
                strength_zh = "统计中等"
            else:
                strength = "STRONG"
                strength_zh = "统计较强"
            verdict["strength"] = strength
            verdict["strength_zh"] = strength_zh
            verdict["strength_basis_zh"] = (
                "按阶段平均相对收益绝对值分层；该强度只描述统计幅度，不改变方向判定。"
            )


def _add_company_selection_reasons(answer: dict[str, Any]) -> None:
    for company in (answer.get("task_answer") or {}).get("company_results") or []:
        disclosures = company.get("pre_event_disclosures") or []
        categories = []
        for row in disclosures:
            label = str(row.get("claim_type") or "")
            if label not in categories:
                categories.append(label)
        category_zh = {
            "BUSINESS_EXPOSURE": "主营业务暴露",
            "GEOGRAPHIC_EXPOSURE": "地域暴露",
            "DEMAND_COST_EXPOSURE": "需求/成本暴露",
        }
        exposure = "、".join(category_zh.get(item, item) for item in categories) or "事件前披露不足"
        company["selection_reason_zh"] = (
            f"按事件前{exposure}、{company.get('industry_name_zh') or '行业'}代表性、"
            f"证据可追溯性和{company.get('trading_status_zh') or '交易状态待核验'}纳入样本。"
        )


def build_qa_records(root: Path) -> QaBundle:
    root = root.resolve()
    base_bundle = _base.build_qa_records(root)
    company_bundle = build_company_ui_bundle(root)
    events = {str(row["event_id"]): row for row in company_bundle["events"]}
    answers: list[dict[str, Any]] = []
    for source in base_bundle.answers:
        answer = dict(source)
        _add_lineage(answer, events[str(answer["event_id"])])
        _add_market_strength(answer)
        _add_company_selection_reasons(answer)
        answers.append(answer)
    return QaBundle(cases=base_bundle.cases, answers=answers, labels=base_bundle.labels)


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
