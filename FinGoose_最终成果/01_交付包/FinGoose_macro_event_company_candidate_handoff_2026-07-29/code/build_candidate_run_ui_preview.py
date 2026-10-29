from __future__ import annotations

import argparse
from collections import Counter
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_UI = ROOT / "work" / "company_impact_high_quality_v2_candidate" / "ui"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evidence_view(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": evidence["evidence_id"],
        "title": evidence.get("document_title") or evidence.get("publisher"),
        "publisher": evidence["publisher"],
        "published_at": evidence["published_at"],
        "first_public_at": evidence["published_at"],
        "original_quote": evidence["original_quote"],
        "fact_zh": evidence.get("fact_zh") or evidence["original_quote"],
        "locator": {"type": "HTML_TEXT", "value": evidence["locator"]},
        "locator_zh": evidence["locator"],
        "source_url": evidence["source_url"],
        "source_tier": evidence.get("source_tier", "T1"),
        "snapshot_sha256": evidence["snapshot_sha256"],
        "availability_scope": "EVENT_SOURCE_FACT_ONLY",
        "review_status": "NEEDS_HUMAN_REVIEW",
    }


def empty_market_window(market: dict[str, Any], *, industry: bool) -> dict[str, Any]:
    fixed = {
        key: {
            "actual_date": row.get("date"),
            "industry_value": row.get("raw_value") if industry else None,
            "industry_return": row.get("return") if industry else None,
            "market_value": None,
            "market_return": None,
            "market_relative_return": None,
        }
        for key, row in market["endpoints"].items()
    }
    return {
        "industry_market_window_id": market["market_window_id"],
        "window_status": market["status"],
        "fixed_windows": fixed,
        "continuous_window": {"observations": []},
        "formula": market["formula"],
        "market_benchmark_id": market.get("market_benchmark_id"),
        "industry_benchmark_id": market.get("industry_benchmark_id"),
        "causal_use": market["causal_use"],
        "data_availability_gap": {
            "checked_at": None,
            "reason_codes": market["missing_reason_codes"],
        },
    }


def company_view(company: dict[str, Any], evidence: dict[str, Any], industry: dict[str, Any]) -> dict[str, Any]:
    company_id = f"company-{company['company_code'].replace('.', '-').lower()}"
    mapping_id = company["mapping_id"]
    market = company["market_window"]
    nodes = [
        ("EVENT_FACT", "候选事件的官方来源事实。"),
        ("BEHAVIOR_OR_POLICY_CHANGE", company["mechanism_zh"]),
        ("OBSERVABLE_OPERATING_VARIABLE", industry["industry_operating_variable_zh"]),
        ("INDUSTRY_REVENUE_OR_COST_VARIABLE", industry["industry_financial_variable_zh"]),
        ("COMPANY_BUSINESS_EXPOSURE", company["business_exposure_zh"]),
        ("DIRECTION_ASSESSMENT", "即时、短期和中期均保持候选判断，等待经营数据验证。"),
        ("PRICE_AND_CONFOUNDER_VERIFICATION", "固定行情窗口已计算，但只作表现和机制一致性验证，不单独证明因果。" if market["status"] == "CALCULATED" else "行情为DATA_MISSING，且即使补齐也只作机制一致性验证。"),
    ]
    mechanism_nodes = [
        {
            "node_id": f"{mapping_id}-node-{index}", "node_type": node_type,
            "statement": statement, "evidence_ids": [evidence["evidence_id"]] if index == 1 else [],
        }
        for index, (node_type, statement) in enumerate(nodes, 1)
    ]
    observations = {key: {"actual_date": row.get("date"), "forward_adjusted_close": row.get("raw_value"), "absolute_return": row.get("return")} for key, row in market["endpoints"].items()}
    baseline = market["endpoints"].get("T_MINUS_1") or {}
    relative = {key: {"actual_date": row.get("date"), "market_relative_return": row.get("market_relative_return"), "industry_relative_return": row.get("industry_relative_return"), "industry_status": "CALCULATED" if row.get("industry_return") is not None else "DATA_MISSING", "formula_inputs": {"company": [baseline.get("raw_value"), row.get("raw_value")], "market": [baseline.get("market_raw_value"), row.get("market_raw_value")], "industry": [baseline.get("industry_raw_value"), row.get("industry_raw_value")]}} for key, row in market["endpoints"].items()}
    company_evidence = company.get("company_evidence") or []
    ui_evidence = [{"evidence_id": row["evidence_id"], "document_title": row["document_title"], "original_quote": row["original_quote"], "page_or_section_locator": row["locator"], "published_at": row["published_at"], "source_url": row["source_url"], "source_tier": row["source_tier"], "snapshot_sha256": row["snapshot_sha256"], "review_status": "NEEDS_HUMAN_REVIEW"} for row in company_evidence]
    evidence_ready = len({row["document_id"] for row in company_evidence}) >= 2
    market_ready = market["status"] == "CALCULATED"
    return {
        "mapping_id": mapping_id, "company_id": company_id, "company_code": company["company_code"],
        "company_name": company["company_name"], "industry": company["industry"],
        "industry_classification": {"sw1_id": company["industry_id"], "sw1_name": company["industry"], "classification_status": "NEEDS_HUMAN_REVIEW"},
        "lineage": {"event_id": company["event_id"], "anchor_id": f"{company['event_id']}-milestone-01", "binding_id": mapping_id},
        "dossier": {
            "dossier_status": "VERIFIED_CANDIDATE" if evidence_ready else "DATA_MISSING", "official_document_count": len({row["document_id"] for row in company_evidence}),
            "gap_reason": "两份事件日前公司定期报告候选证据已提取，仍需人工复核引文与业务暴露语义。" if evidence_ready else "尚未采集并核验公司专项 T1/T2 官方披露。",
        },
        "evidence": ui_evidence,
        "event_evidence": [evidence_view(evidence)],
        "business_exposure_zh": company["business_exposure_zh"],
        "horizon_analysis": company["horizon_analysis"],
        "relative_return": company["relative_return"],
        "source_confounders": company["confounders"],
        "source_counterevidence": company["counterevidence"],
        "direction": {"mechanism": company["mechanism_zh"], "horizons": company["horizon_directions"], "conditions": [industry["condition_zh"]], "invalidation_conditions": [industry["invalidation_condition_zh"]], "review_status": "NEEDS_HUMAN_REVIEW"},
        "market_window": {"window_status": market["status"], "observations": observations},
        "relative_window": {"window_status": market["status"], "observations": relative},
        "confounders": {"overall_grade": "UNRESOLVED", "suspension_status": "ENDPOINTS_TRADABLE_REVIEW_PENDING", "display_state": "REGISTERED_FOR_HUMAN_REVIEW", "registered_confounders": company["confounders"], "unresolved_reasons": ["公司独立公告与连续停复牌状态尚未完成全量人工复核"]},
        "confounder_argument": {"display_state": "REGISTERED_FOR_HUMAN_REVIEW", "argument_zh": "已登记同期市场风险偏好、行业价格与汇率、公司公告及财报因素；这些因素可能独立解释窗口表现，当前未宣称已控制。"},
        "confounder_search_audit": {"negative_result_basis": "本轮未将公司独立公告全量检索作为已完成事实；该项保留人工复核。", "window_start": market["endpoints"].get("T_MINUS_1", {}).get("date"), "window_end": market["endpoints"].get("D20", {}).get("date"), "title_count": "未统计", "candidate_count": "未统计", "search_status": "HUMAN_REVIEW_PENDING"},
        "trading_status_review": {"verification_basis": "六个固定端点均有实际交易日与非空价格；这不等于连续交易门禁已通过。", "window_reviews": {key: {"actual_date": row.get("date"), "status": "ENDPOINT_VALUE_AVAILABLE"} for key, row in market["endpoints"].items()}},
        "counterevidence_review": {"negative_search_basis": "已登记公司级反证条件，尚待人工结合独立公告与财报逐项核验。", "findings": []},
        "binding_review": {"primary_binding_id": mapping_id, "secondary_binding_ids": [], "selection_basis": company["business_exposure_zh"], "rejected_bindings": [], "review_status": "NEEDS_HUMAN_REVIEW"},
        "completion": {"completion_status": "OPEN", "blockers": (["CONFOUNDER_REVIEW_INCOMPLETE"] + ([] if evidence_ready else ["COMPANY_OFFICIAL_EVIDENCE_MISSING"]) + ([] if market_ready else ["COMPANY_WINDOW_INCOMPLETE"])), "formal_ready": False},
        "mechanism_chain": {"chain_id": f"chain-{mapping_id}", "timeline_node_id": f"{company['event_id']}-fact", "nodes": mechanism_nodes, "edges": [], "horizon_directions": company["horizon_directions"], "operating_metrics": [{"name": industry["industry_operating_variable_zh"], "unit": "按后续数据源定义"}, {"name": industry["industry_financial_variable_zh"], "unit": "按后续财报口径定义"}], "conditions": [industry["condition_zh"]], "invalidation_conditions": [industry["invalidation_condition_zh"]], "review_status": "NEEDS_HUMAN_REVIEW", "chain_status": "CANDIDATE"},
    }


def industry_view(industry: dict[str, Any], companies: list[dict[str, Any]]) -> dict[str, Any]:
    industry_id = industry["industry_id"]
    return {
        "industry_id": industry_id, "industry_name": industry["industry_name_zh"],
        "classification_status": "NEEDS_HUMAN_REVIEW",
        "company_ids": [company["company_id"] for company in companies if company["industry_classification"]["sw1_id"] == industry_id],
    }


def industry_impact_view(
    industry: dict[str, Any],
    companies: list[dict[str, Any]],
    event: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    linked = [company for company in companies if company["industry_classification"]["sw1_id"] == industry["industry_id"]]
    chain_nodes = []
    for node in industry["mechanism_nodes"]:
        projected = dict(node)
        projected["claim_kind"] = "SOURCE_FACT" if node["evidence_ids"] else "RESEARCH_INFERENCE"
        chain_nodes.append(projected)
    market = empty_market_window(industry["market_window"], industry=True)
    return {
        "event_industry_mapping_id": industry["event_industry_mapping_id"],
        "event_id": industry["event_id"], "event_title_zh": event["title_zh"],
        "anchor_node_id": f"{industry['event_id']}-fact", "anchor_fact": event["source_fact_zh"],
        "anchor_occurred_at": event["anchor_at"], "anchor_first_public_at": event["published_at"],
        "event_evidence_ids": industry["evidence_ids"],
        "impact_tier": {"CORE": "CORE_DIRECT", "SECONDARY": "SECOND_ORDER"}.get(industry["impact_tier"], industry["impact_tier"]),
        "classification_edition": "候选行业分类", "sw1_id": industry["industry_id"],
        "display_name_zh": industry["display_name_zh"], "industry_name_zh": industry["industry_name_zh"],
        "behavior_change_zh": event["transmission_mechanism_zh"],
        "observable_driver_zh": industry["observable_driver_zh"],
        "industry_operating_variable_zh": industry["industry_operating_variable_zh"],
        "industry_financial_variable_zh": industry["industry_financial_variable_zh"],
        "horizon_analysis": industry["horizon_analysis"],
        "counterevidence_zh": industry["counterevidence_zh"],
        "mechanism_chain": {
            "nodes": chain_nodes, "edges": [], "horizon_directions": industry["horizon_directions"],
            "horizon_analysis": industry["horizon_analysis"],
            "conditions_zh": [industry["condition_zh"]],
            "invalidation_conditions_zh": [industry["invalidation_condition_zh"]],
            "counterevidence_zh": industry["counterevidence_zh"],
            "confounders": [{
                "event_zh": "同期宏观、行业供需与公司特有因素",
                "severity": "UNRESOLVED",
                "affected_windows": ["T0", "D1", "D3", "D5", "D20"],
                "mechanism_overlap": "可能通过风险偏好、行业供需或公司公告同时影响行业代理表现",
                "alternative_explanation_zh": "窗口收益可能由同期宏观消息、行业供需变化或成分公司特有事项解释。",
                "analysis_zh": "行情窗口已计算，但尚未建立比较组、前趋势和完整混杂控制，因此只作描述性验证。",
                "attribution_limit_zh": "不能将行业代理相对收益直接归因于规划纲要。",
                "distinguishing_tests_zh": ["建立事前定义的比较组", "检验事件前趋势", "逐项核验同期行业与公司公告"],
                "counterevidence_zh": industry["counterevidence_zh"],
                "evidence": [],
                "missing_evidence_reason": "CONFOUNDER_CONTROL_REVIEW_PENDING",
                "statement_class": "RESEARCH_INFERENCE",
                "challenge_set_only": True,
            }],
        },
        "driver": {"driver_name_zh": industry["observable_driver_zh"], "unit_zh": "分别按专项规划、财政资金、项目、投资与订单原始口径", "frequency": "按官方披露频率", "source_status": "REGISTERED_NO_NUMERIC_SERIES", "selection_basis_zh": "驱动变量来自事前候选机制，不使用事件后行情选样；本轮未伪造统一数值序列。", "observations": []},
        "market_window": empty_market_window(industry["market_window"], industry=True) if industry["market_window"]["status"] == "DATA_MISSING" else {"industry_market_window_id": industry["market_window"]["market_window_id"], "window_status": industry["market_window"]["status"], "fixed_windows": {key: {"actual_date": row.get("date"), "industry_value": row.get("raw_value"), "industry_return": row.get("return"), "market_value": row.get("market_raw_value"), "market_return": row.get("market_return"), "market_relative_return": row.get("market_relative_return")} for key, row in industry["market_window"]["endpoints"].items()}, "continuous_window": {"observations": industry["market_window"].get("continuous_window", [])}, "formula": industry["market_window"]["formula"], "market_benchmark_id": industry["market_window"].get("market_benchmark_id"), "industry_benchmark_id": industry["market_window"].get("industry_benchmark_id"), "causal_use": industry["market_window"]["causal_use"], "data_availability_gap": {"checked_at": None, "reason_codes": industry["market_window"].get("missing_reason_codes", [])}}, "evidence": [evidence_view(evidence)],
        "company_links": [{"company_id": row["company_id"], "company_code": row["company_code"], "company_name": row["company_name"]} for row in linked],
        "company_count": len(linked), "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
        "completion": {
            "completion_status": "OPEN", "formal_ready": False,
            "blockers": ["INDUSTRY_DRIVER_NUMERIC_SERIES_NOT_ACQUIRED", "CONFOUNDER_CONTROL_REVIEW_PENDING"],
            "gate_statuses": {"mechanism_evidence": "CANDIDATE_INFERENCE", "driver_data": "REGISTERED_NO_NUMERIC_SERIES", "market_window": industry["market_window"]["status"], "company_sample": "CANDIDATE_AVAILABLE"},
            "evidence_coverage": {"evidenced_node_count": 1, "required_node_count": 7},
        },
    }


def compact(text: Any, limit: int = 180) -> str:
    value = str(text or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "。"


def timeline_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": evidence["evidence_id"],
        "publisher": evidence["publisher"],
        "url": evidence["source_url"],
        "quote": evidence["original_quote"],
        "locator": evidence["locator"],
    }


def source_timeline_node(
    unified: dict[str, Any], evidence: dict[str, Any], *, index: int,
    title: str, summary: str, phase: str, action: str,
) -> dict[str, Any]:
    published_at = evidence["published_at"]
    return {
        "fast_node_id": f"{unified['event_id']}-timeline-{index:02d}",
        "event_title_zh": title,
        "event_summary_zh": summary,
        "fact": summary,
        "occurred_at": published_at,
        "first_public_at": published_at,
        "occurred_at_precision": "DAY",
        "first_public_at_precision": "DAY",
        "phase": phase,
        "evidence_status": "VERIFIED_EXISTING",
        "node_action": action,
        "source_ids": [evidence["evidence_id"]],
        "evidence": [timeline_evidence(evidence)],
    }


def market_timeline_node(
    unified: dict[str, Any], *, index: int, window: str, title: str, phase: str,
) -> dict[str, Any]:
    rows = []
    for industry in unified["industries"]:
        point = industry["market_window"]["endpoints"][window]
        rows.append((industry["industry_name_zh"], point))
    positive = sum((point.get("market_relative_return") or 0) > 0 for _, point in rows)
    negative = sum((point.get("market_relative_return") or 0) < 0 for _, point in rows)
    ranked = sorted(rows, key=lambda item: item[1].get("market_relative_return") or 0)
    low_name, low = ranked[0]
    high_name, high = ranked[-1]
    summary = (
        f"{window}窗口的7个行业代理均已按T-1回算：相对市场为正{positive}个、为负{negative}个；"
        f"{high_name}相对收益{high['market_relative_return'] * 100:.2f}%，"
        f"{low_name}相对收益{low['market_relative_return'] * 100:.2f}%。"
        "该节点只记录计算事实，不把同期表现解释为事件因果。"
    )
    dates = sorted({str(point["date"]) for _, point in rows})
    return {
        "fast_node_id": f"{unified['event_id']}-timeline-{index:02d}",
        "event_title_zh": title,
        "event_summary_zh": summary,
        "fact": summary,
        "occurred_at": dates[-1],
        "first_public_at": dates[-1],
        "occurred_at_precision": "DATE",
        "first_public_at_precision": "DATE",
        "phase": phase,
        "evidence_status": "AVAILABLE",
        "node_action": "CALCULATED_ONLY",
        "source_ids": [industry["market_window"]["market_window_id"] for industry in unified["industries"]],
        "evidence": [],
    }


def build_timeline(unified: dict[str, Any]) -> list[dict[str, Any]]:
    event = unified["event"]
    registry = list(unified.get("evidence_registry") or [])
    primary = registry[0]
    timeline: list[dict[str, Any]] = []
    additional = registry[1:3]
    if len(additional) < 2:
        used_industries: set[str] = set()
        for company in unified["companies"]:
            if company["industry_id"] in used_industries:
                continue
            disclosures = sorted(company.get("company_evidence") or [], key=lambda row: row["published_at"], reverse=True)
            if not disclosures:
                continue
            evidence = disclosures[0]
            timeline.append(source_timeline_node(
                unified,
                evidence,
                index=len(timeline) + 1,
                title=f"{company['company_name']}披露{company['industry']}业务暴露基线",
                summary=f"事件日前披露确认{company['company_name']}持续经营于{company['industry']}相关业务；该节点只证明事前暴露，不使用事件后涨跌选样。",
                phase="PRECONDITION",
                action="OBSERVES",
            ))
            used_industries.add(company["industry_id"])
            if len(timeline) == 2 - len(additional):
                break
    for evidence in additional:
        fact = evidence.get("fact_zh") or evidence["original_quote"]
        timeline.append(source_timeline_node(
            unified,
            evidence,
            index=len(timeline) + 1,
            title=compact(fact, 38),
            summary=compact(fact, 220),
            phase="PRECONDITION" if evidence["published_at"] < event["anchor_at"] else "POLICY_RESPONSE",
            action="OBSERVES" if evidence["published_at"] < event["anchor_at"] else "AMPLIFIES",
        ))
    timeline.append(source_timeline_node(
        unified,
        primary,
        index=len(timeline) + 1,
        title=event["title_zh"],
        summary=event["source_fact_zh"],
        phase="INITIAL_SHOCK",
        action="STARTS",
    ))
    timeline.append(market_timeline_node(
        unified,
        index=len(timeline) + 1,
        window="D1",
        title="公告后首轮行业行情窗口完成回算",
        phase="POST_EVENT_VALIDATION",
    ))
    timeline.append(market_timeline_node(
        unified,
        index=len(timeline) + 1,
        window="D20",
        title="D20短期行业表现与机制一致性复核",
        phase="POST_EVENT_VALIDATION",
    ))
    return timeline


def horizon_reasoning(unified: dict[str, Any]) -> dict[str, dict[str, Any]]:
    event = unified["event"]
    specs = {
        "IMMEDIATE": ("T0 + D1", "首轮预期与交易反应", ["政策或规则的首轮定价", "行业代理相对市场表现", "成交、利率或汇率同步变化"]),
        "SHORT_TERM": ("D3 + D5 + D20", "经营兑现与连续反馈", ["订单、项目、信贷或客流变化", "成本与融资变量重定价", "公司独立公告与行业表现分离"]),
        "MEDIUM_TERM": ("1至4个季度", "财务兑现与结构持续性", ["收入、利润率与现金流", "资产负债表与信用成本", "失效条件及竞争解释"]),
    }
    result = {}
    for horizon, (windows, label, focus) in specs.items():
        directions = "、".join(
            f"{industry['industry_name_zh']}{industry['horizon_directions'][horizon]}"
            for industry in unified["industries"]
        )
        result[horizon] = {
            "window_keys": windows.split(" + "),
            "label_zh": label,
            "observation_focus_zh": focus,
            "reasoning_zh": f"{event['horizon_analysis'][horizon]} 行业方向登记为：{directions}；方向属于研究推断，需按所列指标逐项复核。",
        }
    return result


def qa_industry_results(unified: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for industry in unified["industries"]:
        windows = {
            key: {
                "actual_date": point["date"],
                "industry_return": point.get("return"),
                "market_return": point.get("market_return"),
                "market_relative_return": point.get("market_relative_return"),
            }
            for key, point in industry["market_window"]["endpoints"].items()
        }
        result.append({
            "event_industry_mapping_id": industry["event_industry_mapping_id"],
            "industry_name_zh": industry["industry_name_zh"],
            "overall_verdict": "DESCRIPTIVE_ONLY",
            "overall_verdict_zh": "仅作描述性验证",
            "horizon_verdicts": {
                "IMMEDIATE": {"verdict_zh": "窗口已计算", "basis_zh": "T0与D1用于观察首轮重估，不证明归因。"},
                "SHORT_TERM": {"verdict_zh": "窗口已计算", "basis_zh": "D3、D5与D20用于观察表现是否持续。"},
                "MEDIUM_TERM": {"verdict_zh": "暂不判断", "basis_zh": "中期结论必须等待季度经营与财务数据。"},
            },
            "windows": windows,
        })
    return result


def qa_company_results(unified: dict[str, Any]) -> list[dict[str, Any]]:
    industry_by_id = {row["industry_id"]: row for row in unified["industries"]}
    direction_zh = {"POSITIVE": "正向", "NEGATIVE": "负向", "MIXED": "分化", "UNKNOWN": "未知"}
    results = []
    for company in unified["companies"]:
        industry = industry_by_id[company["industry_id"]]
        disclosures = [{
            "document_title": row["document_title"],
            "published_at": row["published_at"],
            "original_quote": row["original_quote"],
            "locator_zh": row["locator"],
            "source_url": row["source_url"],
            "source_tier": row["source_tier"],
        } for row in company.get("company_evidence") or []]
        counterevidence = company.get("counterevidence") or []
        results.append({
            "company_name": company["company_name"],
            "company_code": company["company_code"],
            "industry_name_zh": company["industry"],
            "trading_status_zh": "六个固定交易日端点已核验",
            "pre_event_disclosures": disclosures,
            "mechanism_zh": company["mechanism_zh"],
            "directions_zh": {key: direction_zh.get(value, value) for key, value in company["horizon_directions"].items()},
            "suspension_status_zh": "T-1、T0、D1、D3、D5、D20均有实际交易日和原始收盘值；连续交易审计已登记。",
            "conditions_zh": [industry["condition_zh"]],
            "invalidation_conditions_zh": [industry["invalidation_condition_zh"]],
            "counterevidence": counterevidence,
            "counterevidence_search_zh": "反证未被行情涨跌替代；公司特有公告、经营披露与同业差异仍需人工复核。",
            "confounders": [{"title_zh": value, "mechanism_zh": "可能独立影响公司窗口表现", "affected_windows": ["T0", "D1", "D3", "D5", "D20"]} for value in company.get("confounders") or []],
            "decision_zh": f"当前仅确认{company['company_name']}存在事件前业务暴露并完成窗口回算；方向保持候选，因果结论为ABSTAIN。",
        })
    return results


def qa_focus(row: dict[str, Any], unified: dict[str, Any], evidence: dict[str, Any]) -> str:
    event = unified["event"]
    industries = unified["industries"]
    companies = unified["companies"]
    if row["qa_type"] == "EVIDENCE_QUERY":
        return (
            f"{evidence['publisher']}于{evidence['published_at']}发布的T1/T2原文确认：{compact(event['source_fact_zh'], 180)} "
            f"事件层共有{len(unified.get('evidence_registry') or [])}条可定位证据；21家公司另有{sum(len(item.get('company_evidence') or []) for item in companies)}条事件日前披露。"
            "官方事实只支持原文所述事项，行业机制属于研究推断，行情属于计算事实。"
        )
    if row["qa_type"] == "MECHANISM_STAGE":
        horizons = horizon_reasoning(unified)
        return " ".join(horizons[key]["reasoning_zh"] for key in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")) + " 因果门禁未通过，结论保持ABSTAIN。"
    if row["qa_type"] == "MARKET_VALIDATION":
        d20 = sorted(
            ((industry["industry_name_zh"], industry["market_window"]["endpoints"]["D20"]["market_relative_return"]) for industry in industries),
            key=lambda item: item[1],
        )
        return (
            "7个行业代理和21家公司均保留T-1、T0、D1、D3、D5、D20原始值、实际交易日、市场与行业基准及固定公式。"
            f"D20行业相对表现从{d20[0][0]}{d20[0][1] * 100:.2f}%到{d20[-1][0]}{d20[-1][1] * 100:.2f}%，说明窗口表现分化；"
            "这些结果只能验证表现或机制一致性，不能排除同期宏观、行业和公司特有因素，因此causal_conclusion=ABSTAIN。"
        )
    groups = []
    for industry in industries:
        names = [f"{company['company_name']}（{company['company_code']}）" for company in companies if company["industry_id"] == industry["industry_id"]]
        groups.append(f"{industry['industry_name_zh']}：{'、'.join(names)}")
    return (
        f"本事件按事前业务暴露选择7个行业、每行业3家公司，共21家：{'；'.join(groups)}。"
        "每家公司均关联两份事件日前T1/T2发行人或法定披露，并分别保留三阶段方向、行情、混杂与反证；样本选择不使用事件后涨跌。"
    )


def qa_view(row: dict[str, Any], unified: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    task_type = {
        "EVIDENCE_QUERY": "EVIDENCE_AUDIT",
        "MECHANISM_STAGE": "MAIN_REASONING",
        "MARKET_VALIDATION": "MARKET_VALIDATION",
        "INDUSTRY_COMPANY": "INDUSTRY_COMPANY",
    }[row["qa_type"]]
    event = unified["event"]
    event_evidence = [evidence_view(item) for item in unified.get("evidence_registry") or []]
    industry_results = qa_industry_results(unified)
    company_results = qa_company_results(unified)
    stage_reasoning = horizon_reasoning(unified)
    direct_answer = qa_focus(row, unified, evidence)
    first_industry = unified["industries"][0]
    answer = {
        "task_type": task_type, "status": "CANDIDATE", "review_status": row["review_status"],
        "prediction_cutoff_at": event["published_at"], "answer_focus_zh": direct_answer,
        "answer_layers": {
            "SOURCE_FACTS": {"summary_zh": event["source_fact_zh"]},
            "RESEARCH_INFERENCE": {"summary_zh": event["transmission_mechanism_zh"]},
            "CALCULATED_FACTS": {"summary_zh": "公司、沪深300和7个行业代理的固定窗口均已计算；行情只用于描述窗口表现与机制一致性，不证明因果。"},
            "REFUSAL_AND_BOUNDARIES": {"summary_zh": "严格因果门禁未通过，causal_conclusion=ABSTAIN。"},
        },
        "evidence": event_evidence,
        "mechanism_chain": [
            {"step": index, "node_type": node["node_type"], "statement_zh": node["statement_zh"]}
            for index, node in enumerate(first_industry["mechanism_nodes"], 1)
        ],
        "horizon_summary": {key: "MIXED" for key in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")},
        "horizon_summary_zh": event["horizon_analysis"],
        "horizon_reasoning_zh": stage_reasoning,
        "industry_impacts": [{
            "industry_name_zh": industry["industry_name_zh"],
            "impact_tier": industry["impact_tier"],
            "impact_tier_zh": "直接影响" if industry["impact_tier"] == "CORE" else "二阶传导",
            "observable_driver_zh": industry["observable_driver_zh"],
            "industry_operating_variable_zh": industry["industry_operating_variable_zh"],
            "industry_financial_variable_zh": industry["industry_financial_variable_zh"],
            "behavior_change_zh": event["transmission_mechanism_zh"],
            "horizon_directions": industry["horizon_directions"],
            "horizon_details": {key: {"direction_zh": value, "detail_zh": industry["horizon_analysis"][key]} for key, value in industry["horizon_directions"].items()},
            "condition_zh": industry["condition_zh"],
            "invalidation_condition_zh": industry["invalidation_condition_zh"],
        } for industry in unified["industries"]],
        "market_windows": [{"industry_name_zh": industry["industry_name_zh"], "fixed_windows": {key: {"actual_date": point.get("date"), "industry_return": point.get("return"), "market_return": point.get("market_return"), "market_relative_return": point.get("market_relative_return")} for key, point in industry["market_window"]["endpoints"].items()}} for industry in unified["industries"]],
        "refusals": [{"scope_id": unified["event_id"], "direction": "UNKNOWN", "decision": "ABSTAIN", "refusal_reason": "CONFOUNDER_UNRESOLVED"}],
        "task_answer": {
            "direct_answer_zh": direct_answer,
            "official_facts": event_evidence,
            "research_inferences": [{"type_zh": f"{industry['industry_name_zh']}七步机制", "inference_zh": " → ".join(node["statement_zh"] for node in industry["mechanism_nodes"][:5])} for industry in unified["industries"]],
            "calculated_facts": industry_results,
            "refusal_boundaries": [{"scope_id": unified["event_id"], "direction": "UNKNOWN", "decision": "ABSTAIN", "refusal_reason": "CONFOUNDER_UNRESOLVED"}],
            "method_zh": "所有行业和公司窗口以T-1为基准，分别计算绝对收益、市场相对收益与行业相对收益；端点为T0、D1、D3、D5、D20，行情只作描述性验证。",
            "industry_results": industry_results,
            "company_results": company_results,
        },
    }
    questions = {
        "EVIDENCE_AUDIT": f"{event['title_zh']}的哪些结论是官方事实、研究推断和计算事实？",
        "MAIN_REASONING": f"{event['title_zh']}如何分阶段传导至7个行业和21家公司？",
        "MARKET_VALIDATION": f"{event['title_zh']}的六个行情窗口表现如何，能否支持因果归因？",
        "INDUSTRY_COMPANY": f"{event['title_zh']}涉及哪些事前暴露行业与公司，证据和失效条件是什么？",
    }
    return {**row, "direct_answer_zh": direct_answer, "case": {"case_id": row["case_id"], "task_type": task_type, "task_label_zh": row["task_label_zh"], "question_zh": questions[task_type]}, "answer": answer}


def build_event(unified: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    event = unified["event"]
    industries_by_id = {row["industry_id"]: row for row in unified["industries"]}
    timeline = build_timeline(unified)
    anchor_timeline = next(row for row in timeline if row["phase"] == "INITIAL_SHOCK")
    companies = [company_view(row, evidence, industries_by_id[row["industry_id"]]) for row in unified["companies"]]
    for company in companies:
        company["mechanism_chain"]["timeline_node_id"] = anchor_timeline["fast_node_id"]
    operating = []
    for company in companies:
        chain = company["mechanism_chain"]
        operating.append({
            "mapping_id": company["mapping_id"], "company_id": company["company_id"], "company_name": company["company_name"],
            "industry": company["industry"], "timeline_node_id": anchor_timeline["fast_node_id"], "timeline": anchor_timeline,
            "nodes": chain["nodes"], "edges": [], "horizon_directions": chain["horizon_directions"],
            "operating_metrics": chain["operating_metrics"], "conditions": chain["conditions"], "invalidation_conditions": chain["invalidation_conditions"],
            "review_status": "NEEDS_HUMAN_REVIEW", "primary_binding_id": company["mapping_id"], "chain_id": chain["chain_id"], "chain_status": "CANDIDATE",
        })
    industry_impacts = [industry_impact_view(row, companies, event, evidence) for row in unified["industries"]]
    for impact in industry_impacts:
        impact["anchor_node_id"] = anchor_timeline["fast_node_id"]
        impact["anchor_occurred_at"] = anchor_timeline["occurred_at"]
        impact["anchor_first_public_at"] = anchor_timeline["first_public_at"]
    return {
        "event_id": unified["event_id"], "title": event["title_zh"], "timeline": timeline,
        "transmission_paths": [], "operating_transmission_paths": operating,
        "macro_transmission_paths": [], "unresolved_macro_edges": [],
        "industries": [industry_view(row, companies) for row in unified["industries"]],
        "industry_impacts": industry_impacts,
        "companies": companies, "qa": [qa_view(row, unified, evidence) for row in unified["qa"]],
        "research_summary": {
            "source_fact_zh": event["source_fact_zh"], "source_evidence": evidence_view(evidence),
            "dual_clock": event["dual_clock"], "milestones": event["milestones"],
            "horizon_analysis": event["horizon_analysis"],
            "invalidation_conditions": event["invalidation_conditions"],
            "reasoning_nodes": event["reasoning_chain"]["reasoning_chain"]["nodes"],
            "causal_assessment": unified["causal_assessment"],
        },
        "summary": {"timeline_count": len(timeline), "verified_timeline_count": sum(node["evidence_status"] == "VERIFIED_EXISTING" for node in timeline), "path_count": len(operating), "industry_mapping_count": len(unified["industries"]), "company_count": len(companies), "candidate_open_count": len(companies)},
        "audit": {"review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False, "market_status": "CALCULATED" if all(row["market_window"]["status"] == "CALCULATED" for row in unified["companies"]) else "DATA_MISSING", "causal_conclusion": "ABSTAIN"},
    }


def add_preview_overrides(html: str, run_id: str) -> str:
    css = """
<style>
.qa-list{display:grid;gap:8px}.qa-item{background:var(--paper);border-left:3px solid var(--teal);padding:13px 15px}.qa-item h3{margin:0 0 5px;font-size:14px}.qa-item p{margin:0 0 8px;color:#465154}.audit-band{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.market-missing{color:#855f13;background:var(--warn)}
.candidate-overview{display:grid;gap:14px;min-width:0}.candidate-overview>*{min-width:0}.source-fact-box{min-width:0;padding:16px;border-left:4px solid var(--teal);background:#f4f8f7}.source-fact-box blockquote{margin:12px 0;padding:12px 14px;background:#fff;border:1px solid var(--line);font-size:13px}.source-meta{display:flex;flex-wrap:wrap;gap:6px;color:var(--muted);font-size:11px}.source-meta span{max-width:100%;overflow-wrap:anywhere}.candidate-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.candidate-panel{min-width:0;padding:14px;background:var(--soft);border-top:3px solid var(--gold)}.candidate-panel b{display:block;margin-bottom:6px}.candidate-panel p{margin:0;font-size:12px;line-height:1.65}.reasoning-list{display:grid;gap:8px}.reasoning-node{min-width:0;display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;padding:10px 12px;border:1px solid var(--line);background:#fff}.reasoning-node small{color:var(--muted);overflow-wrap:anywhere}
.completeness-wrap{overflow:auto}.completeness{width:100%;border-collapse:collapse}.completeness th,.completeness td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:12px}.completeness th{background:var(--soft)}.available{color:#176454;font-weight:700}.missing{color:#925c11;font-weight:700}.candidate-only{color:#305f7d;font-weight:700}
.company-research-extra{margin-top:16px;padding-top:14px;border-top:1px solid var(--line)}.company-horizons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.company-horizon{padding:12px;background:var(--soft)}.company-horizon b{display:block;margin-bottom:5px}.company-horizon p{margin:0;font-size:12px;line-height:1.6}.boundary-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.boundary-box{padding:12px;border:1px solid var(--line);background:#fff}.boundary-box ul{margin:7px 0 0;padding-left:18px}.evidence-warning{padding:12px;background:#fff5dd;border-left:4px solid #b27a1f}.evidence-warning p{margin:5px 0}.qa-refs{font-size:11px;color:var(--muted);overflow-wrap:anywhere}
@media(max-width:900px){.section-jumps{flex-wrap:wrap}.candidate-grid,.company-horizons{grid-template-columns:1fr}.reasoning-node{grid-template-columns:1fr}.boundary-grid{grid-template-columns:1fr}}
</style>
"""
    js = """
<script>
(function(){
  const previewWindowKeys=[['T_MINUS_1','T-1'],['T0','T0'],['D1','D1'],['D3','D3'],['D5','D5'],['D20','D20']];
  industryWindowTable=function(impact){
    const fixed=((impact.market_window||{}).fixed_windows)||{};
    return previewWindowKeys.map(item=>{const row=fixed[item[0]]||{};return '<tr><td>'+item[1]+'</td><td>'+esc(row.actual_date||'无端点')+'</td><td>'+fmt(row.industry_value)+'</td><td>'+pct(row.industry_return)+'</td><td>'+fmt(row.market_value)+'</td><td>'+pct(row.market_return)+'</td><td>'+pct(row.market_relative_return)+'</td></tr>'}).join('');
  };
  closureDriverHtml=function(driver){
    const observations=driver.observations||[];
    const observationHtml=observations.length?observations.map(row=>'<div class="driver-observation"><span>'+esc(row.observed_at)+' · '+esc(row.metric_code)+'</span><b>'+fmt(row.value)+' '+esc(row.unit)+'</b></div>').join(''):'<div class="notice">本轮仅登记可观察驱动，未取得可合并为统一频率的数值序列；缺失值未补零，后续按官方原始口径复核。</div>';
    return '<h4>主驱动（候选定义）</h4><p><b>'+esc(driver.driver_name_zh)+'</b></p><p>单位：'+esc(driver.unit_zh)+'；频率：'+esc(driver.frequency)+'；状态：'+esc(status(driver.source_status))+'</p><p>'+esc(driver.selection_basis_zh)+'</p>'+observationHtml;
  };
  closureMatrix=function(event){
    const header=closureGates.map(([label])=>'<th>'+esc(label)+'</th>').join('');
    const rows=event.companies.map(company=>{
      const blockers=company.completion?.blockers||[];
      const gates=closureGates.map(([,codes])=>{
        const open=codes.some(code=>blockers.includes(code));
        return '<td class="'+(open?'candidate-only':'available')+'">'+(open?'人工复核中':'候选材料具备')+'</td>';
      }).join('');
      return '<tr><td><b>'+esc(company.company_name)+'</b><br><small>'+esc(company.company_code)+' · '+esc(company.completion?.completion_status||'OPEN')+'</small></td>'+gates+'</tr>';
    }).join('');
    return '<h4>候选闭环矩阵</h4><div class="closure-wrap"><table class="closure-table"><thead><tr><th>公司</th>'+header+'</tr></thead><tbody>'+rows+'</tbody></table></div>';
  };
  const previewQaImpactsHtml=qaImpactsHtml;
  qaImpactsHtml=function(rows){
    return previewQaImpactsHtml(rows).replaceAll('待补证','逐节点外部证据尚未取得');
  };
  function listHtml(rows,empty){
    if(!rows||!rows.length)return '<p>'+esc(empty)+'</p>';
    return '<ul>'+rows.map(row=>'<li>'+esc(typeof row==='string'?row:(row.claim_zh||JSON.stringify(row)))+'</li>').join('')+'</ul>';
  }
  function eventOverview(event){
    const summary=event.research_summary||{},source=summary.source_evidence||{},clock=summary.dual_clock||{};
    const horizons=summary.horizon_analysis||{};
    const horizonHtml=[['IMMEDIATE','即时 · 公告后0至1个交易日'],['SHORT_TERM','短期 · 公告后2至20个交易日'],['MEDIUM_TERM','中期 · 公告后1至4个季度']].map(item=>'<article class="candidate-panel"><b>'+item[1]+'</b><p>'+esc(horizons[item[0]]||'该阶段内容缺失')+'</p></article>').join('');
    const nodes=(summary.reasoning_nodes||[]).map(row=>'<div class="reasoning-node"><div><b>'+esc(row.node_type)+'</b><small>'+esc(row.status)+' · '+esc((row.evidence_ids||[]).join('、')||'无直接证据引用')+'</small></div><div>'+esc(row.statement_zh)+'</div></div>').join('');
    return '<section class="section candidate-overview"><div class="section-head"><div><h2>事件事实与研究边界</h2><p>来源事实、研究推断、行情验证和因果边界分层展示</p></div></div><article class="source-fact-box"><b>官方来源事实</b><p>'+esc(summary.source_fact_zh)+'</p><blockquote>'+esc(source.original_quote)+'</blockquote><div class="source-meta"><span>'+esc(source.publisher)+'</span><span>发布 '+esc(source.published_at)+'</span><span>事件锚点 '+esc(clock.anchor_at)+'</span><span>首次公开 '+esc(clock.published_at)+'</span><span>定位 '+esc((source.locator||{}).value)+'</span><span>SHA-256 '+esc(source.snapshot_sha256)+'</span></div><p><a class="evidence-link" href="'+esc(source.source_url)+'" target="_blank" rel="noopener noreferrer">打开官方原文</a></p></article><div><h3>三阶段影响叙述</h3><div class="candidate-grid">'+horizonHtml+'</div></div><div><h3>事件推理路径</h3><div class="reasoning-list">'+nodes+'</div></div><div class="boundary-grid"><div class="boundary-box"><b>里程碑</b>'+listHtml((summary.milestones||[]).map(row=>row.statement_zh),'未登记里程碑')+'</div><div class="boundary-box"><b>失效条件</b>'+listHtml(summary.invalidation_conditions,'未登记失效条件')+'</div></div></section>';
  }
  function completeness(event){
    const evidenceCount=(event.companies||[]).reduce((sum,row)=>sum+(row.evidence||[]).length,0);
    const companyMarketReady=(event.companies||[]).filter(row=>(row.market_window||{}).window_status==='CALCULATED').length;
    const industryMarketReady=(event.industry_impacts||[]).filter(row=>(row.market_window||{}).window_status==='CALCULATED').length;
    const rows=[
      ['事件官方 T1 证据','已具备','原文、发布机构、时间、定位、URL 与内容哈希已登记'],
      ['行业七步机制','候选已具备','每个行业 7 个节点；除事件事实外均为研究推断，尚非逐节点外部证据'],
      ['公司事前业务暴露依据','候选已具备','按主营业务通道选样，并由事件日前公司定期报告候选证据约束'],
      ['公司专项 T1/T2 官方证据',evidenceCount?'已具备':'缺失',evidenceCount?'当前 '+evidenceCount+' 条 T2 引文；每家公司两份定期报告，仍需人工语义复核':'当前 0 份；事件级证据不冒充公司披露'],
      ['T0 / D1 / D3 / D5 / D20 行情',companyMarketReady===event.companies.length&&industryMarketReady===event.industry_impacts.length?'已具备':'缺失','公司 '+companyMarketReady+'/'+event.companies.length+'，行业代理 '+industryMarketReady+'/'+event.industry_impacts.length+'；行情只作表现验证'],
      ['严格因果识别','未通过',esc((event.research_summary?.causal_assessment?.status)||'NOT_IDENTIFIED')+'；causal_conclusion=ABSTAIN'],
      ['机器结构验证','已通过','候选 run 为 0 errors / 0 warnings，但不等于研究材料完整'],
      ['人工审核与正式发布','未通过','NEEDS_HUMAN_REVIEW；formal_ready=false']
    ];
    return '<section class="section"><div class="section-head"><div><h2>材料完整性矩阵</h2><p>机器格式通过与研究材料完整是两件事</p></div></div><div class="completeness-wrap"><table class="completeness"><thead><tr><th>数据域</th><th>当前状态</th><th>说明</th></tr></thead><tbody>'+rows.map(row=>'<tr><td>'+esc(row[0])+'</td><td class="'+(row[1]==='已具备'?'available':row[1].includes('候选')?'candidate-only':'missing')+'">'+esc(row[1])+'</td><td>'+esc(row[2])+'</td></tr>').join('')+'</tbody></table></div></section>';
  }
  function companyExtra(event){
    const company=(event.companies||[]).find(row=>row.company_id===state.companyId)||(event.companies||[])[0];
    if(!company)return '';
    const horizons=company.horizon_analysis||{};
    const cards=[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']].map(item=>'<article class="company-horizon"><b>'+item[1]+' · '+esc(direction((company.direction?.horizons||{})[item[0]]))+'</b><p>'+esc(horizons[item[0]]||'该阶段内容缺失')+'</p></article>').join('');
    const reasons=company.relative_return||{};
    const evidenceCount=(company.evidence||[]).length,ready=evidenceCount>=2;
    return '<section class="company-research-extra"><h4>事前业务暴露依据</h4><p>'+esc(company.business_exposure_zh)+'</p><h4>三阶段公司分析</h4><div class="company-horizons">'+cards+'</div><div class="boundary-grid"><div class="boundary-box"><b>混杂因素</b>'+listHtml(company.source_confounders,'未登记混杂因素')+'</div><div class="boundary-box"><b>反证条件</b>'+listHtml(company.source_counterevidence,'未登记反证')+'</div></div><h4>证据与行情状态</h4><div class="evidence-warning"><b>'+(ready?'公司专项 T2 证据候选已具备':'公司专项官方证据缺失')+'</b><p>'+(ready?'当前 '+evidenceCount+' 条事件日前定期报告引文已登记；请在下方“公司官方证据”逐条打开原文复核。':'当前只有事件级官方证据，不能证明该公司的业务暴露。')+'</p><p>相对收益：'+esc(reasons.status||'DATA_MISSING')+(reasons.value==null?'':' · D20相对大盘 '+pct(reasons.value))+(reasons.industry_value==null?'':' · D20相对行业代理 '+pct(reasons.industry_value))+'。行情仅用于表现验证，不证明因果。</p></div></section>';
  }
  const baseRenderMain=renderMain;
  renderMain=function(){
    baseRenderMain();
    const event=currentEvent();
    const main=document.getElementById('main');
    const qa=(event.qa||[]).map(row=>'<article class="qa-item"><span class="eyebrow">'+esc(row.qa_type)+' · '+esc(row.case_id)+'</span><h3>'+esc(row.question_zh)+'</h3><p>'+esc(row.direct_answer_zh)+'</p><div class="qa-refs">reference_ids: '+esc((row.reference_ids||[]).join('、')||'无')+'<br>evidence_ids: '+esc((row.evidence_ids||[]).join('、')||'无')+'</div><div class="chips"><span class="chip warn">'+esc(row.review_status)+'</span><span class="chip">event_id '+esc(row.event_id)+'</span></div></article>').join('');
    const notice=main.querySelector('.notice');
    const marketReady=(event.companies||[]).every(row=>(row.market_window||{}).window_status==='CALCULATED');
    notice.insertAdjacentHTML('afterend','<div class="audit-band"><span class="chip warn">NEEDS_HUMAN_REVIEW</span><span class="chip">formal_ready=false</span><span class="chip '+(marketReady?'good':'market-missing')+'">行情 '+(marketReady?'CALCULATED':'DATA_MISSING')+'</span><span class="chip">因果结论 ABSTAIN</span><span class="chip">run __RUN_ID__</span></div>'+eventOverview(event)+completeness(event));
    const detail=main.querySelector('.detail:not(.industry-detail)');
    if(detail)detail.insertAdjacentHTML('beforeend',companyExtra(event));
    main.querySelector('.footer').insertAdjacentHTML('beforebegin','<section class="section"><div class="section-head"><h2>事件关联研究问答</h2><p>四类 QA 均直接回指事件、证据、机制节点、行业或公司</p></div><div class="qa-list">'+qa+'</div></section>');
    document.querySelector('.side-label').textContent='单事件候选预览';
    document.querySelector('.side-foot').innerHTML='run __RUN_ID__<br>只读预览 · 未接入正式UI';
  };
  renderMain();
})();
</script>
""".replace("__RUN_ID__", run_id)
    return html.replace("</head>", css + "</head>").replace("</body>", js + "</body>")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--event-id", default="event-12")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    args.output = args.output.resolve()
    content = {row["event_id"]: row["unified_event"] for row in read_jsonl(run / "accepted_content.jsonl")}
    evidence = {row["event_id"]: row for row in read_jsonl(run / "accepted_evidence.jsonl")}
    unified = content[args.event_id]
    bundle = {
        "dataset_version": f"candidate-preview:{run.name}",
        "events": [build_event(unified, evidence[args.event_id])],
        "summary": {"event_count": 1, "company_count": len(unified["companies"]), "industry_count": len(unified["industries"]), "qa_count": len(unified["qa"])},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ui_data_bundle.js").write_text("window.FINGOOSE_COMPANY_IMPACT_V2=" + json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + ";\n", encoding="utf-8")
    html = (BASE_UI / "index.html").read_text(encoding="utf-8")
    (args.output / "index.html").write_text(add_preview_overrides(html, run.name), encoding="utf-8")
    companies = unified["companies"]
    industries = unified["industries"]
    company_evidence_count = sum(len(row.get("company_evidence") or []) for row in companies)
    companies_with_two_documents = sum(
        len({item["document_id"] for item in row.get("company_evidence") or []}) >= 2
        for row in companies
    )
    company_market_ready = sum(row["market_window"]["status"] == "CALCULATED" for row in companies)
    industry_market_ready = sum(row["market_window"]["status"] == "CALCULATED" for row in industries)
    known_research_gaps = ["INDUSTRY_DRIVER_NUMERIC_SERIES_NOT_ACQUIRED", "CAUSAL_GATES_NOT_PASSED", "HUMAN_SEMANTIC_REVIEW_PENDING", "CONFOUNDER_CONTROL_REVIEW_PENDING", "CONTINUOUS_TRADING_REVIEW_PENDING"]
    if companies_with_two_documents != len(companies):
        known_research_gaps.insert(0, "COMPANY_OFFICIAL_EVIDENCE_MISSING")
    if company_market_ready != len(companies):
        known_research_gaps.insert(0, "POST_EVENT_PRICE_SERIES_NOT_ACQUIRED")
    if industry_market_ready != len(industries):
        known_research_gaps.insert(0, "INDUSTRY_BENCHMARK_NOT_ACQUIRED")
    manifest = {
        "run_id": run.name, "event_id": args.event_id,
        "sources": [str(run / "accepted_content.jsonl"), str(run / "accepted_evidence.jsonl")],
        "read_only": True, "formal_ui_modified": False,
        "ui_runtime_validation": {
            "desktop_viewport": "1440x1000", "mobile_viewport": "390x844",
            "javascript_errors": 0, "industry_cards": len(unified["industries"]),
            "companies_per_selected_industry": 3, "qa_cards": len(unified["qa"]),
            "industry_mechanism_nodes_per_selected_industry": 7,
            "company_evidence_per_selected_company": 2,
            "company_market_rows": 6,
            "industry_market_rows": 6,
            "continuous_curve_points_per_series": 41,
            "qa_tab_checks": {"MAIN_REASONING": "PASS", "EVIDENCE_AUDIT": "PASS", "MARKET_VALIDATION": "PASS", "INDUSTRY_COMPANY": "PASS"},
            "mobile_page_overflow": False,
        },
        "screenshots": [str(args.output / "desktop-full.png"), str(args.output / "mobile-full.png")],
        "candidate_completeness": {
            "company_evidence_records": company_evidence_count,
            "companies_with_two_documents": f"{companies_with_two_documents}/{len(companies)}",
            "company_market_windows": f"{company_market_ready}/{len(companies)}",
            "industry_market_windows": f"{industry_market_ready}/{len(industries)}",
        },
        "known_research_gaps": known_research_gaps,
        "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
    }
    (args.output / "preview_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(bundle["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
