"""Normalize UI research material into the research-content-v1 contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
CONTENT_SCHEMA_VERSION = "research-content-v1"


class ContentAlignmentError(ValueError):
    """Raised when a UI event cannot satisfy the content contract."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _evidence_ids(value: Any) -> list[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in {"evidence_ids", "event_evidence_ids", "source_ids"} and isinstance(child, list):
                    found.update(str(v) for v in child if v)
                elif key in {"evidence_id", "source_id"} and child:
                    found.add(str(child))
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(found)


def _collect_evidence(value: Any) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            evidence_id = item.get("evidence_id") or item.get("source_id")
            if evidence_id:
                key = str(evidence_id)
                if key not in found:
                    found[key] = {
                        "evidence_id": key,
                        "title": item.get("title"),
                        "publisher": item.get("publisher") or item.get("publisher_zh"),
                        "published_at": item.get("published_at") or item.get("first_public_at"),
                        "locator": item.get("locator") or item.get("locator_zh"),
                        "original_quote": item.get("original_quote") or item.get("quote"),
                        "source_url": item.get("source_url") or item.get("url"),
                        "sha256": item.get("sha256") or item.get("snapshot_sha256"),
                        "review_status": item.get("review_status"),
                        "formal_ready": item.get("formal_ready"),
                        "missing": not bool(item.get("original_quote") or item.get("quote"))
                        or not bool(item.get("locator") or item.get("locator_zh")),
                    }
                else:
                    current = found[key]
                    aliases = {
                        "title": item.get("title"),
                        "publisher": item.get("publisher") or item.get("publisher_zh"),
                        "published_at": item.get("published_at") or item.get("first_public_at"),
                        "locator": item.get("locator") or item.get("locator_zh") or item.get("page_or_section_locator"),
                        "original_quote": item.get("original_quote") or item.get("quote"),
                        "source_url": item.get("source_url") or item.get("url"),
                        "sha256": item.get("sha256") or item.get("snapshot_sha256"),
                        "review_status": item.get("review_status"),
                        "formal_ready": item.get("formal_ready"),
                    }
                    for field, child in aliases.items():
                        if child not in (None, "") and current.get(field) in (None, ""):
                            current[field] = child
                    current["missing"] = not bool(
                        current.get("original_quote")
                        and current.get("locator")
                        and current.get("source_url")
                    )
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return [found[key] for key in sorted(found)]


def _source_facts(ui_event: Mapping[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in ui_event.get("timeline") or []:
        if not isinstance(row, Mapping):
            continue
        node_id = _text(row.get("fast_node_id"))
        statement = _text(row.get("event_summary_zh") or row.get("event_title_zh"))
        if not node_id or not statement:
            continue
        facts.append(
            {
                "node_id": node_id,
                "statement_zh": statement,
                "fact_zh": _text(row.get("fact")),
                "occurred_at": row.get("occurred_at"),
                "first_public_at": row.get("first_public_at"),
                "evidence_ids": _evidence_ids(row),
                "evidence_status": row.get("evidence_status") or "PENDING_EVIDENCE",
                "phase": row.get("phase"),
                "visibility": row.get("visibility"),
            }
        )
    return facts


def _mechanism_nodes(impact: Mapping[str, Any]) -> list[dict[str, Any]]:
    chain = impact.get("mechanism_chain") or {}
    nodes = chain.get("nodes") if isinstance(chain, Mapping) else []
    result: list[dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, Mapping) or not node.get("node_id"):
            continue
        result.append(
            {
                "node_id": str(node["node_id"]),
                "node_type": node.get("node_type"),
                "statement_zh": _text(node.get("statement_zh") or node.get("inference_zh")),
                "evidence_ids": _evidence_ids(node),
                "premise_node_ids": [str(v) for v in node.get("premise_node_ids") or []],
                "status": node.get("status") or node.get("evidence_status"),
            }
        )
    return result


def _horizon_block(impacts: Sequence[Mapping[str, Any]], horizon: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for impact in impacts:
        directions = impact.get("horizon_directions") or {}
        direction = directions.get(horizon) if isinstance(directions, Mapping) else None
        nodes = _mechanism_nodes(impact)
        direction_node = next(
            (node for node in nodes if node.get("node_type") == "DIRECTION_ASSESSMENT"),
            None,
        )
        detail = _text(direction_node.get("statement_zh") if direction_node else "")
        name = _text(impact.get("display_name_zh") or impact.get("industry_name_zh"))
        if not name or not direction:
            continue
        summary = f"{name}：{direction}。"
        if detail:
            summary += detail
        rows.append(
            {
                "scope_id": impact.get("event_industry_mapping_id"),
                "scope_name_zh": name,
                "direction": str(direction),
                "detail_zh": detail or summary,
                "condition_zh": impact.get("condition_zh"),
                "invalidation_condition_zh": impact.get("invalidation_condition_zh"),
                "mechanism_node_ids": [node["node_id"] for node in nodes],
                "evidence_ids": sorted(
                    set(_evidence_ids(impact))
                    | {eid for node in nodes for eid in node["evidence_ids"]}
                ),
            }
        )
    if not rows:
        raise ContentAlignmentError(f"missing {horizon} content")
    return {
        "summary_zh": "；".join(row["detail_zh"] for row in rows[:3]),
        "impact_rows": rows,
        "mechanism_node_ids": sorted(
            {node_id for row in rows for node_id in row["mechanism_node_ids"]}
        ),
        "evidence_ids": sorted({eid for row in rows for eid in row["evidence_ids"]}),
    }


def _industry_content(impact: Mapping[str, Any]) -> dict[str, Any]:
    nodes = _mechanism_nodes(impact)
    directions = impact.get("horizon_directions") or {}
    if not all(_text(directions.get(horizon)) for horizon in HORIZONS):
        raise ContentAlignmentError(
            f"{impact.get('event_industry_mapping_id')}: incomplete horizon directions"
        )
    return {
        "event_industry_mapping_id": impact.get("event_industry_mapping_id"),
        "industry_name_zh": impact.get("display_name_zh") or impact.get("industry_name_zh"),
        "impact_tier": impact.get("impact_tier"),
        "observable_driver_zh": impact.get("observable_driver_zh"),
        "industry_operating_variable_zh": impact.get("industry_operating_variable_zh"),
        "industry_financial_variable_zh": impact.get("industry_financial_variable_zh"),
        "condition_zh": impact.get("condition_zh"),
        "invalidation_condition_zh": impact.get("invalidation_condition_zh"),
        "counterevidence_zh": deepcopy(impact.get("counterevidence_zh") or []),
        "review_status": impact.get("review_status") or "NEEDS_HUMAN_REVIEW",
        "formal_ready": bool(impact.get("formal_ready", False)),
        "causal_attribution_allowed": bool(impact.get("causal_attribution_allowed", False)),
        "horizon_directions": {horizon: directions.get(horizon) for horizon in HORIZONS},
        "mechanism_nodes": nodes,
        "evidence_ids": sorted(set(_evidence_ids(impact))),
    }


def _company_content(company: Mapping[str, Any]) -> dict[str, Any]:
    direction = company.get("direction") or {}
    dossier = company.get("dossier") or {}
    confounders = company.get("confounders") or []
    counterevidence = company.get("counterevidence_review") or {}
    business = dossier.get("business_exposure") or {}
    if isinstance(business, Mapping):
        business_text = _text(
            business.get("exposure_zh")
            or business.get("business_exposure_zh")
            or business.get("summary_zh")
        )
    else:
        business_text = _text(business)
    return {
        "mapping_id": company.get("mapping_id"),
        "company_code": company.get("company_code"),
        "company_name": company.get("company_name"),
        "business_exposure_zh": business_text or _text(company.get("industry")),
        "mechanism_zh": direction.get("mechanism"),
        "horizon_directions": direction.get("horizons") or {},
        "conditions": direction.get("conditions") or [],
        "invalidation_conditions": direction.get("invalidation_conditions") or [],
        "counterevidence": deepcopy(counterevidence.get("findings") or []),
        "confounder_argument_zh": (company.get("confounder_argument") or {}).get("argument_zh")
        if isinstance(company.get("confounder_argument"), Mapping)
        else _text(company.get("confounder_argument")),
        "review_status": direction.get("review_status") or "NEEDS_HUMAN_REVIEW",
        "formal_ready": bool(direction.get("formal_ready", False)),
        "causal_attribution_allowed": bool(
            (confounders.get("causal_attribution_allowed") if isinstance(confounders, Mapping) else False)
        ),
        "evidence_ids": _evidence_ids(company),
        "market_window": deepcopy(company.get("market_window") or {}),
    }


def _qa_content(qa: Mapping[str, Any]) -> dict[str, Any]:
    case = qa.get("case") or {}
    answer = qa.get("answer") or {}
    task_answer = answer.get("task_answer") or {}
    layers = answer.get("answer_layers") or {}

    source_layer = layers.get("SOURCE_FACTS") or {}
    official_facts = deepcopy(task_answer.get("official_facts") or [])
    if not official_facts:
        official_facts = [
            {
                "evidence_id": row.get("evidence_id"),
                "fact_zh": row.get("fact_zh") or row.get("summary_zh"),
                "original_quote": row.get("original_quote"),
                "locator": row.get("locator") or row.get("locator_zh"),
                "publisher": row.get("publisher") or row.get("publisher_zh"),
                "published_at": row.get("first_public_at"),
                "source_url": row.get("source_url"),
            }
            for row in source_layer.get("evidence") or []
            if isinstance(row, Mapping) and row.get("evidence_id")
        ]

    inference_layer = layers.get("RESEARCH_INFERENCE") or {}
    research_inferences = deepcopy(task_answer.get("research_inferences") or [])
    if not research_inferences:
        mechanism = inference_layer.get("mechanism_chain") or []
        if isinstance(mechanism, Mapping):
            mechanism = mechanism.get("nodes") or []
        research_inferences = [
            {
                "node_type": row.get("node_type"),
                "inference_zh": row.get("statement_zh") or row.get("inference_zh"),
                "evidence_ids": [str(value) for value in row.get("evidence_ids") or [] if value],
                "condition_zh": row.get("condition_zh"),
                "invalidation_zh": row.get("invalidation_zh"),
            }
            for row in mechanism
            if isinstance(row, Mapping) and (row.get("statement_zh") or row.get("inference_zh"))
        ]
        if not research_inferences and inference_layer.get("summary_zh"):
            research_inferences = [{
                "inference_zh": inference_layer.get("summary_zh"),
                "evidence_ids": _evidence_ids(inference_layer),
            }]

    calculated_layer = layers.get("CALCULATED_FACTS") or {}
    calculated_facts = deepcopy(task_answer.get("calculated_facts") or [])
    if not calculated_facts:
        windows = calculated_layer.get("market_windows") or answer.get("market_windows") or []
        results_by_id = {
            str(row.get("event_industry_mapping_id")): row
            for row in task_answer.get("industry_results") or []
            if isinstance(row, Mapping) and row.get("event_industry_mapping_id")
        }
        calculated_facts = []
        for row in windows:
            if not isinstance(row, Mapping):
                continue
            normalized = deepcopy(dict(row))
            verdict = results_by_id.get(str(row.get("event_industry_mapping_id")))
            if verdict:
                normalized["overall_verdict"] = verdict.get("overall_verdict")
                normalized["overall_verdict_zh"] = verdict.get("overall_verdict_zh")
                normalized["horizon_verdicts"] = deepcopy(verdict.get("horizon_verdicts") or {})
            normalized["method_zh"] = task_answer.get("method_zh") or calculated_layer.get("method_zh")
            calculated_facts.append(normalized)

    boundary_layer = layers.get("REFUSAL_AND_BOUNDARIES") or {}
    refusal_boundaries = deepcopy(
        task_answer.get("refusal_boundaries")
        or answer.get("refusals")
        or boundary_layer.get("refusals")
        or []
    )
    return {
        "case_id": case.get("case_id"),
        "task_type": case.get("task_type"),
        "task_label_zh": case.get("task_label_zh"),
        "question_zh": case.get("question_zh"),
        "direct_answer_zh": task_answer.get("direct_answer_zh") or answer.get("answer_focus_zh"),
        "official_facts": official_facts,
        "research_inferences": research_inferences,
        "calculated_facts": calculated_facts,
        "refusal_boundaries": refusal_boundaries,
        "industry_results": deepcopy(task_answer.get("industry_results") or []),
        "company_results": deepcopy(task_answer.get("company_results") or []),
        "method_zh": task_answer.get("method_zh") or calculated_layer.get("method_zh"),
        "horizon_reasoning_zh": deepcopy(answer.get("horizon_reasoning_zh") or {}),
        "research_conclusion_zh": answer.get("research_conclusion_zh") or inference_layer.get("research_conclusion_zh"),
        "review_status": case.get("review_status") or "NEEDS_HUMAN_REVIEW",
        "formal_ready": bool(case.get("formal_ready", False)),
        "evidence_ids": _evidence_ids(qa),
    }


def _statement_map(
    source_facts: Sequence[Mapping[str, Any]],
    industries: Sequence[Mapping[str, Any]],
    event_id: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for fact in source_facts:
        statement = _text(fact.get("statement_zh"))
        node_id = _text(fact.get("node_id"))
        if statement and node_id:
            result[node_id] = statement
    for industry in industries:
        for node in industry.get("mechanism_nodes") or []:
            if node.get("node_id") and node.get("statement_zh"):
                result[str(node["node_id"])] = str(node["statement_zh"])
    # These synthetic labels are present in the existing event compiler.
    prefix = f"{event_id}-"
    result.setdefault(prefix + "shock", "该宏观事件形成公开冲击，并通过风险偏好、需求和流动性渠道传导。")
    result.setdefault(prefix + "channel-risk-appetite", "风险偏好下降，避险需求和波动率上升。")
    result.setdefault(prefix + "channel-global-demand", "全球需求和跨境活动受到冲击，行业经营变量随之变化。")
    result.setdefault(prefix + "channel-safe-haven-demand", "避险资产需求上升，汇率和利率定价出现相应变化。")
    for asset, label in {
        "sp500": "S&P 500 作为风险资产价格窗口，用于检验市场是否同步反应。",
        "vixcls": "波动率指数作为风险偏好窗口，用于检验不确定性定价。",
        "dcoilwtico": "WTI 原油价格作为全球需求窗口，用于检验能源需求变化。",
        "dexchus": "人民币兑美元汇率作为避险和流动性窗口，用于检验市场反应。",
    }.items():
        result.setdefault(f"{prefix}intermediate-{asset}", label)
        result.setdefault(f"{prefix}asset-{asset}", label)
    result.setdefault(prefix + "market-validation", "固定行情窗口只用于验证市场反应，不证明严格因果。")
    return result


def build_event_research_content(ui_event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _text(ui_event.get("event_id"))
    if not event_id:
        raise ContentAlignmentError("event_id is required")
    source_facts = _source_facts(ui_event)
    impacts = [row for row in ui_event.get("industry_impacts") or [] if isinstance(row, Mapping)]
    industries = [_industry_content(row) for row in impacts]
    companies = [_company_content(row) for row in ui_event.get("companies") or [] if isinstance(row, Mapping)]
    qa_sections = [_qa_content(row) for row in ui_event.get("qa") or [] if isinstance(row, Mapping)]
    horizon_analysis = {horizon: _horizon_block(impacts, horizon) for horizon in HORIZONS}
    evidence_registry = _collect_evidence(ui_event)
    primary_fact = next((fact for fact in source_facts if fact.get("phase") == "INITIAL_SHOCK"), None)
    preconditions = [fact["node_id"] for fact in source_facts if fact.get("phase") == "PRECONDITION"]
    main_path = [fact["node_id"] for fact in source_facts if fact.get("phase") == "INITIAL_SHOCK"]
    if primary_fact:
        main_path += [f"{event_id}-shock", f"{event_id}-channel-risk-appetite", f"{event_id}-intermediate-sp500", f"{event_id}-asset-sp500", f"{event_id}-market-validation"]
    else:
        main_path = [fact["node_id"] for fact in source_facts[:1]] + [f"{event_id}-market-validation"]
    boundaries = {
        "causal_claim_allowed": False,
        "market_is_validation_only": True,
        "review_status": ui_event.get("review_status") or "NEEDS_HUMAN_REVIEW",
        "limitations_zh": "候选材料仍需人工审核；行情窗口只验证同步反应，不能单独证明事件因果。",
    }
    return {
        "schema_version": CONTENT_SCHEMA_VERSION,
        "event_id": event_id,
        "title_zh": _text(ui_event.get("title") or ui_event.get("title_zh") or event_id),
        "source_facts": source_facts,
        "macro_mechanism": {
            "paths": deepcopy(ui_event.get("macro_transmission_paths") or ui_event.get("transmission_paths") or []),
            "summary_zh": "；".join(_text(row.get("event_summary_zh")) for row in ui_event.get("macro_transmission_paths") or [] if _text(row.get("event_summary_zh")))[:1200],
        },
        "horizon_analysis": horizon_analysis,
        "market_validation": deepcopy(ui_event.get("industry_market_windows") or ui_event.get("market_windows") or []),
        "industry_impacts": industries,
        "company_impacts": companies,
        "qa_sections": qa_sections,
        "evidence_registry": evidence_registry,
        "main_path_node_ids": main_path,
        "precondition_node_ids": preconditions,
        "statement_by_node_id": _statement_map(source_facts, industries, event_id),
        "boundaries": boundaries,
        "review_state": {
            "formal_ready": bool(ui_event.get("formal_ready", False)),
            "review_status": ui_event.get("review_status") or "NEEDS_HUMAN_REVIEW",
            "sha_gate": ui_event.get("sha_gate") or "DEFERRED",
        },
        "answer_evidence_ids": sorted(
            set(_evidence_ids(ui_event))
            | {eid for horizon in horizon_analysis.values() for eid in horizon["evidence_ids"]}
        ),
        "primary_answer_evidence_ids": [fact["evidence_ids"][0] for fact in source_facts if fact.get("evidence_ids")][:3],
    }


def select_task_content(event: Mapping[str, Any], sample: Mapping[str, Any]) -> dict[str, Any]:
    content = event.get("research_content") or {}
    task_type = sample.get("task_type")
    if task_type == "EVENT_ANALYSIS":
        return deepcopy(content)
    if task_type == "INDUSTRY_IMPACT":
        ids = set((sample.get("metadata") or {}).get("related_industry_ids") or [])
        return next((deepcopy(row) for row in content.get("industry_impacts", []) if row.get("event_industry_mapping_id") in ids), {})
    if task_type == "COMPANY_IMPACT":
        codes = set((sample.get("metadata") or {}).get("related_company_codes") or [])
        return next((deepcopy(row) for row in content.get("company_impacts", []) if row.get("company_code") in codes), {})
    if task_type == "EVENT_QA":
        case_id = str(sample.get("sample_id", "")).split("-qa-", 1)[-1]
        return next((deepcopy(row) for row in content.get("qa_sections", []) if str(row.get("case_id")) == case_id), {})
    return {}


__all__ = [
    "CONTENT_SCHEMA_VERSION", "ContentAlignmentError", "HORIZONS",
    "build_event_research_content", "select_task_content",
]
